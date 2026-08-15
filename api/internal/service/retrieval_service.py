#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/16 13:57
@Author     : 歌白
@File       : retrieval_service.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import Flask
from injector import inject
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document as LCDocument
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool, tool
from sqlalchemy import update

from internal.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from internal.entity.dataset_entity import RetrievalStrategy, RetrievalSource
from internal.exception import NotFoundException
from internal.lib.helper import combine_documents
from internal.model import Dataset, DatasetQuery, Segment
from pkg.my_sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .jieba_service import JiebaService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class RetrievalService(BaseService):
    """检索服务"""
    db: SQLAlchemy
    vector_database_service: VectorDatabaseService
    jieba_service: JiebaService

    def search_in_datasets(
            self,
            dataset_ids: list[UUID],
            query: str,
            account_id: UUID,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
            k: int = 4,
            score: float = 0,
            retrival_source: str = RetrievalSource.HIT_TESTING,
    ) -> list[LCDocument]:
        """
        知识库检索的核心方法。

        整体流程：
        1. 校验权限 → 2. 构建检索器 → 3. 按策略执行检索 → 4. 记录查询日志 → 5. 更新命中计数

        参数说明：
        - dataset_ids: 要检索的知识库ID列表（前端传入的可能包含无权限的ID，会在这里过滤掉）
        - query: 用户的搜索问题
        - retrieval_strategy: 检索策略，支持三种：
            * semantic（语义检索）：将 query 转为向量，在向量库中找最相似的文档片段
            * full_text（全文检索）：用 jieba 分词后，在 PostgreSQL 中做关键词匹配
            * hybrid（混合检索）：同时跑语义+全文，用 RRF(Reciprocal Rank Fusion) 融合两组结果
        - k: 最终返回的文档数量上限
        - score: 语义检索时的最低相似度阈值，低于此分数的结果会被过滤
        - retrival_source: 调用来源标记（如 hit_testing 命中测试、agent 智能体调用等），写入日志用
        """
        # ========== 第1步：权限校验 + 过滤无效知识库 ==========
        # 前端传的 dataset_ids 可能包含不属于当前用户的ID，
        # 这里用 account_id 做过滤，确保只检索有权限的知识库。
        datasets = self.db.session.query(Dataset).filter(
            Dataset.id.in_(dataset_ids),
            Dataset.account_id == account_id,
        ).all()
        if datasets is None or len(datasets) == 0:
            raise NotFoundException("当前无知识库可执行检索")
        # 用过滤后的合法ID覆盖原始列表
        dataset_ids = [dataset.id for dataset in datasets]

        # ========== 第2步：构建三种检索器 ==========
        # 延迟导入避免循环依赖
        from internal.core.retrievers import SemanticRetriever, FullTextRetriever

        # 2.1 语义检索器：基于向量相似度，在 Weaviate/向量库中查找
        semantic_retriever = SemanticRetriever(
            dataset_ids=dataset_ids,
            vector_store=self.vector_database_service.vector_store,  # Weaviate 向量存储实例
            search_kwargs={
                "k": k,  # 返回结果数量
                "score_threshold": score,  # 相似度阈值，低于此分数的丢弃
            },
        )

        # 2.2 全文检索器：基于 jieba 分词 + PostgreSQL ILIKE 做关键词匹配
        full_text_retriever = FullTextRetriever(
            db=self.db,
            dataset_ids=dataset_ids,
            jieba_service=self.jieba_service,  # 中文分词服务
            search_kwargs={
                "k": k,  # 返回结果数量
            },
        )

        # 2.3 混合检索器：包装语义+全文两个检索器，LangChain 的 EnsembleRetriever
        # 内部使用 RRF 算法融合两路结果：
        #   RRF_score(doc) = Σ 1/(k + rank_i(doc))
        #   weights=[0.5, 0.5] 表示两路权重各占一半
        hybrid_retriever = EnsembleRetriever(
            retrievers=[semantic_retriever, full_text_retriever],
            weights=[0.5, 0.5]
        )

        # ========== 第3步：根据策略执行检索 ==========
        # invoke(query) 会调用检索器的 _get_relevant_documents 方法
        # [:k] 截断确保不超过 k 条（混合检索可能在融合时返回多于 k 的结果）
        if retrieval_strategy == RetrievalStrategy.SEMANTIC:
            lc_documents = semantic_retriever.invoke(query)[:k]
        elif retrieval_strategy == RetrievalStrategy.FULL_TEXT:
            lc_documents = full_text_retriever.invoke(query)[:k]
        else:
            lc_documents = hybrid_retriever.invoke(query)[:k]

        # ========== 第4步：记录查询日志 ==========
        # 每次检索都写入 DatasetQuery 表，方便后续分析用户搜了什么、命中了哪些知识库
        for lc_document in lc_documents:
            self.create(
                DatasetQuery,
                dataset_id=lc_document.metadata["dataset_id"],  # 从文档元数据中取知识库ID
                query=query,
                source=retrival_source,  # 区分是命中测试还是正式调用
                # todo:等待APP配置模版完成后进行调整
                source_app_id=None,
                created_by=account_id,
            )

        # ========== 第5步：批量更新命中次数 ==========
        # 用一条 SQL UPDATE 批量更新所有被命中片段的 hit_count + 1
        # 优势：避免循环中逐条 update，减少数据库往返次数
        with self.db.auto_commit():
            stmt = (
                update(Segment)
                .where(
                    Segment.id.in_(
                        [lc_document.metadata["segment_id"] for lc_document in lc_documents]
                    )
                )
                .values(hit_count=Segment.hit_count + 1)  # SQL层面自增，避免并发问题
            )
            self.db.session.execute(stmt)

        return lc_documents

    def create_langchain_tool_from_search(
            self,
            flask_app: Flask,
            dataset_ids: list[UUID],
            account_id: UUID,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
            k: int = 4,
            score: float = 0,
            retrival_source: str = RetrievalSource.HIT_TESTING,
    ) -> BaseTool:
        """根据传递的参数构建一个LangChain知识库搜索工具"""

        class DatasetRetrievalInput(BaseModel):
            """知识库检索工具输入结构"""
            query: str = Field(description="知识库搜索query语句，类型为字符串")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """如果需要搜索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""

            # 1.调用search_in_datasets检索得到LangChain文档列表
            with flask_app.app_context():
                documents = self.search_in_datasets(
                    dataset_ids=dataset_ids,
                    query=query,
                    account_id=account_id,
                    retrieval_strategy=retrieval_strategy,
                    k=k,
                    score=score,
                    retrival_source=retrival_source,
                )

            # 2.将LangChain文档列表转换成字符串后返回
            if len(documents) == 0:
                return "知识库内没有检索到的对应内容"
            
            return combine_documents(documents)

        return dataset_retrieval

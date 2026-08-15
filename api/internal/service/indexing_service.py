#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/13 17:59
@Author     : 歌白
@File       : indexing_service.py
"""
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.entity.cache_entity import (
    LOCK_DOCUMENT_UPDATE_ENABLED
)
from internal.entity.dataset_entity import DocumentStatus
from internal.entity.dataset_entity import SegmentStatus
from internal.exception import NotFoundException
from internal.lib.helper import generate_text_hash
from internal.model import Document, Segment, KeywordTable, DatasetQuery
from pkg.my_sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .process_rule_service import ProcessRuleService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class IndexingService(BaseService):
    """索引构建服务以及异步任务逻辑处理"""
    file_extractor: FileExtractor
    db: SQLAlchemy
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    vector_database_service: VectorDatabaseService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    redis_client: Redis

    def build_documents(self, document_ids: list[UUID]):
        """根据传递的文档id列表构建知识库文档，涵盖了加载，分割，索引构建，数据存储等内容"""
        # 1.根据传递的文档id获取所有文档
        documents = self.db.session.query(Document).filter(
            Document.id.in_(document_ids)
        ).all()

        # 2.执行循环遍历所有文档完成对每个文档的构建
        for document in documents:
            try:
                # 3.更新当前状态为解析中，并记录开始处理的时间
                self.update(
                    document,
                    status=DocumentStatus.PARSING,
                    processing_started_at=datetime.now()
                )
                # 4.执行文档加载步骤，并更新文档的状态与时间
                lc_documents = self._parsing(document)

                # 5.执行文档分割步骤，并更新文档状态与世界，涵盖了片段的信息
                lc_segments = self._splitting(document, lc_documents)

                # 6.执行文档索引构建，涵盖关键词提取、向量，并更新数据状态
                self._indexing(document, lc_segments)
                # 7.存储操作，涵盖文档状态更新，以及向量数据库的存储
                self._completed(document, lc_segments)

            except Exception as e:
                logging.exception("构建文档发生错误，错误信息：%(error)s", {"error": e})
                self.update(
                    document,
                    status=DocumentStatus.ERROR,
                    error=str(e),
                    stopped_at=datetime.now()
                )

    def update_document_enabled(self, document_id: UUID) -> None:
        """根据传递的文档id更新文档状态，同时修改weaviate向量数据库中的记录"""
        # 1.构建缓存键
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)
        # 2.根据传递的document_id获取文档记录
        document = self.get(Document, document_id)
        if document is None:
            logging.exception(f"当前文件不存在，文档id:{document_id}")
            raise NotFoundException("当前文件不存在")
        # 3.查询归属于当前的文档的所有片段的节点id（仅COMPLETED用于向量DB）
        segments = self.db.session.query(Segment).with_entities(
            Segment.id,
            Segment.node_id,
            Segment.enabled
        ).filter(
            Segment.document_id == document_id,
            Segment.status == SegmentStatus.COMPLETED,
        ).all()
        segment_ids = [id for id, _, _ in segments]
        node_ids = [node_id for _, node_id, _ in segments]
        logging.info(f"segment_ids: {segment_ids}, node_ids: {node_ids}")

        try:
            # 4.执行循环遍历所有node_ids并更新向量数据库
            collection = self.vector_database_service.collection
            for node_id in node_ids:
                try:
                    collection.data.update(
                        uuid=node_id,
                        properties={
                            "document_enabled": document.enabled,
                        }
                    )
                except Exception as e:
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id == node_id,
                        ).update({
                            "error": str(e),
                            "status": SegmentStatus.ERROR,
                            "enabled": False,
                            "disabled_at": datetime.now(),
                            "stopped_at": datetime.now(),
                        })

            # 5.查询所有片段的id（不限status，因为_indexing会把所有segment的id写入keyword_table）
            all_segment_ids = [
                id for id, in self.db.session.query(Segment).with_entities(Segment.id).filter(
                    Segment.document_id == document_id,
                ).all()
            ]
            # 6.更新关键词表对应的数据（enabled为false表示从关键词表中删除数据，enabled为true表示在关键词表中新增数据）
            if document.enabled is True:
                # 7.从禁用改为启用，需要新增关键词（只新增处于启用状态的COMPLETED片段）
                enabled_segment_ids = [id for id, _, enabled in segments if enabled is True]
                self.keyword_table_service.add_keyword_table_from_ids(
                    document.dataset_id,
                    enabled_segment_ids,
                )
            else:
                # 8.从启用改为禁用，需要剔除所有片段的关联关键词
                self.keyword_table_service.delete_keyword_table_from_ids(
                    document.dataset_id,
                    all_segment_ids,
                )


        except Exception as e:
            # 5.记录日志并将状态修改回原来的状态
            logging.exception(f"修改向量数据库文档启用状态是吧，文档id:{document_id},错误信息：{str(e)}")
            origin_enabled = not document.enabled
            self.update(
                document,
                enabled=origin_enabled,
                disabled_at=None if origin_enabled else datetime.now()
            )
        finally:
            # 6.清空缓存键标识异步操作已经执行完成，无论失败还是成功
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """根据传递的知识库id+文档id删除文档信息"""
        # 1.查找该文档下的所有片段id列表
        segment_ids = [
            str(id) for id, in self.db.session.query(Segment).with_entities(Segment.id).filter(
                Segment.document_id == document_id,
            ).all()
        ]
        # 2.调用向量数据库删除其相关记录
        collection = self.vector_database_service.collection
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(document_id)
        )

        # 3.删除postgres关联的segment记录
        with self.db.auto_commit():
            self.db.session.query(Segment).filter(
                Segment.document_id == document_id
            ).delete()

        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segment_ids)

        # # 4.记录需要删除的片段id集合和空关键词列表
        # segment_ids_to_delete = set(segment_ids)
        # keywords_to_delete = set()
        #
        # # 5.更新知识库关键词表信息，并且该操作需要上锁，避免并发更新的时候出现关键词映射错误的问题
        # cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        # with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
        #     # 6.获取当前知识库的关键词
        #     keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(dataset_id)
        #     keyword_table = keyword_table_record.keyword_table.copy()
        #
        #     # 7.循环遍历所有关键词执行判断与更新
        #     for keyword, ids in keyword_table.items():
        #         ids_set = set(ids)
        #         if segment_ids_to_delete.intersection(ids_set):
        #             keyword_table[keyword] = list(ids_set.difference(segment_ids_to_delete))
        #             if not keyword_table[keyword]:
        #                 keywords_to_delete.add(keyword)
        #
        #     # 8.检测空关键词数据并删除（关键词并没有映射任何字段id的数据）
        #     for keyword in keywords_to_delete:
        #         del keyword_table[keyword]
        #
        #     # 9.将数据更新到关键词中
        #     self.update(keyword_table_record, keyword_table=keyword_table)

    def _indexing(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """根据传递的信息构建索引，涵盖关键词提取，词表构建"""
        for lc_segment in lc_segments:
            # 1.提取每一个片段对应的关键词，关键词的数量最多不超过10个
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            # 2.逐条更新文档片段的关键词
            self.db.session.query(Segment).filter(
                Segment.id == lc_segment.metadata["segment_id"]
            ).update({
                "keywords": keywords,
                "status": SegmentStatus.INDEXING,
                "indexing_completed_at": datetime.now(),
            })
            # 3.获取当前知识库的关键词表
            keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(document.dataset_id)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }
            # 4.循环将新关键词添加到关键词表中
            for keyword in keywords:
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])

            # 5.更新关键词表
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()}
            )

        # 6.更新文档状态
        self.update(
            document,
            indexing_completed_at=datetime.now()
        )

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """存储文档片段到向量数据库，并完成状态更新"""
        # 1.循环遍历片段列表数据，将文档状态及片段状态设置成True
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        # 2.调用向量数据库，每次存储10条数据，避免一次传递过多的数据
        try:
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                self.vector_database_service.vector_store.add_documents(chunks, ids=ids)
                with self.db.auto_commit():
                    self.db.session.query(Segment).filter(
                        Segment.node_id.in_(ids)
                    ).update({
                        "status": SegmentStatus.COMPLETED,
                        "completed_at": datetime.now(),
                        "enabled": True,
                    })
        except Exception as e:
            logging.exception(
                "构建文档片段索引发生异常, 错误信息: %(error)s",
                {"error": e},
            )
            with self.db.auto_commit():
                self.db.session.query(Segment).filter(
                    Segment.node_id.in_(ids)
                ).update({
                    "status": SegmentStatus.ERROR,
                    "completed_at": None,
                    "stopped_at": datetime.now(),
                    "enabled": False,
                    "error": str(e),
                })

        # 6.更新文档的状态数据
        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True,
        )

    def _completed__del(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """存储文档片段到向量数据库，并完成状态更新"""
        # 1.循环遍历片段列表数据，将文档状态及片段状态设置成True
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        def thread_func(flask_app: Flask, chunk: list[LCDocument], IDS: list[UUID]) -> None:
            """线程函数，执行向量数据库与postgres数据的存储"""
            with flask_app.app_context():
                try:
                    self.vector_database_service.vector_store.add_documents(chunks, ids=ids)
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.COMPLETED,
                            "completed_at": datetime.now(),
                            "enabled": True,
                        })
                except Exception as e:
                    logging.exception(f"构建文档片段索引发生异常，错误信息：{str(e)}")
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.ERROR,
                            "completed_at": None,
                            "stopped_at": datetime.now(),
                            "enabled": False,
                            "error": str(e)
                        })

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                futures.append(executor.submit(thread_func, current_app._get_current_object(), chunks, ids))
            for future in futures:
                future.result()
            # 2.调用向量数据库，每次存储10条数据，避免一次传递过多的数据
            # try:
            #     for i in range(0, len(lc_segments), 10):
            #         chunks = lc_segments[i:i + 10]
            #         ids = [chunk.metadata["node_id"] for chunk in chunks]
            #         self.vector_database_service.vector_store.add_documents(chunks, ids=ids)
            #
            #         with self.db.auto_commit():
            #             self.db.session.query(Segment).filter(
            #                 Segment.node_id.in_(ids)
            #             ).update({
            #                 "status": SegmentStatus.COMPLETED,
            #                 "completed_at": datetime.now(),
            #                 "enabled": True,
            #             })
            # except Exception as e:
            #     logging.exception(
            #         "构建文档片段索引发生异常，错误信息：%{error}s",
            #         {"error": e},
            #     )
            #
            #     with self.db.auto_commit():
            #         self.db.session.query(Segment).filter(
            #             Segment.node_id.in_(ids)
            #         ).update({
            #             "status": SegmentStatus.ERROR,
            #             "completed_at": None,
            #             "stopped_at": datetime.now(),
            #             "enabled": False,
            #             "error": str(e)
            #         })

        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True
        )

    def delete_dataset(self, dataset_id: UUID) -> None:
        """根据传递的知识库id执行响应的删除操作"""
        try:
            with self.db.auto_commit():
                # 1.删除关联的文档记录
                self.db.session.query(Document).filter(
                    Document.dataset_id == dataset_id,
                ).delete()

                # 2.删除关联的片段记录
                self.db.session.query(Segment).filter(
                    Segment.dataset_id == dataset_id,
                ).delete()

                # 3.删除关联的关键词表记录
                self.db.session.query(KeywordTable).filter(
                    KeywordTable.dataset_id == dataset_id,
                ).delete()

                # 4.删除知识库查询记录
                self.db.session.query(DatasetQuery).filter(
                    DatasetQuery.dataset_id == dataset_id,
                ).delete()

            # 5.调用向量数据库删除知识库的关联记录
            self.vector_database_service.collection.data.delete_many(
                where=Filter.by_property("dataset_id").equal(str(dataset_id))
            )

        except Exception as e:
            logging.exception(f"")

    def _parsing(self, document: Document) -> list[LCDocument]:
        """解析传递的文档为LangChain文档列表"""
        # 1.获取upload_file并加载LangChain文档
        upload_file = document.upload_file
        lc_documents = self.file_extractor.load(upload_file, False, True)

        # 2.循环处理LangChain文档，并删除多余的空白字符串
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # 3.更新文档状态并记录时间
        self.update(
            document,
            character_count=sum([len(lc_document.page_content) for lc_document in lc_documents]),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(),
        )

        return lc_documents

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """清除过滤传递的多余空白字符串"""
        text = re.sub(r'<\|', '<', text)
        text = re.sub(r'\|>', '>', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]', '', text)
        text = re.sub('\uFFFE', '', text)  # 删除零宽非标记字符
        return text

    def _splitting(self, document: Document, lc_documents: list[LCDocument]) -> list[LCDocument]:
        """根据传递的信息进行文档分割，拆分成小块片段"""
        try:
            # 1.根据process_rule获取文本分割器
            process_rule = document.process_rule
            text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
                process_rule,
                self.embeddings_service.calculate_token_count,
            )

            # 2.按照process_rule规则清除多余的字符串
            for lc_document in lc_documents:
                lc_document.page_content = self.process_rule_service.clean_text_by_process_rule(
                    lc_document.page_content,
                    process_rule,
                )

            # 3.分割文档列表为片段列表
            lc_segments = text_splitter.split_documents(lc_documents)

            # 4.获取对应文档下得到最大片段位置
            position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
                Segment.document_id == document.id,
            ).scalar()

            # 5.循环处理片段数据并添加元数据，同时存储到postgres数据库中
            segments = []
            for lc_segment in lc_segments:
                position += 1
                content = lc_segment.page_content
                segment = self.create(
                    Segment,
                    account_id=document.account_id,
                    dataset_id=document.dataset_id,
                    document_id=document.id,
                    node_id=uuid.uuid4(),
                    position=position,
                    content=content,
                    character_count=len(content),
                    token_count=self.embeddings_service.calculate_token_count(content),
                    hash=generate_text_hash(content),
                    status=SegmentStatus.WAITING,
                )
                lc_segment.metadata = {
                    "account_id": str(document.account_id),
                    "dataset_id": str(document.dataset_id),
                    "document_id": str(document.id),
                    "segment_id": str(segment.id),
                    "node_id": str(segment.node_id),
                    "document_enabled": False,
                    "segment_enabled": False,
                }
                segments.append(segment)

            # 6.更新文档的数据，涵盖状态、token数等内容
            self.update(
                document,
                token_count=sum([segment.token_count for segment in segments]),
                status=DocumentStatus.INDEXING,
                splitting_completed_at=datetime.now(),
            )

            return lc_segments
        except Exception as e:
            print("_splitting出现异常:", e)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/1 21:53
@Author     : 歌白
@File       : dataset_retrieval_node.py
"""
import time
from typing import Optional, Any
from uuid import UUID

from flask import Flask
from langchain_core.pydantic_v1 import PrivateAttr
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .dataset_retrieval_entity import DatasetRetrievalNodeData


class DatasetRetrievalNode(BaseNode):
    node_data: DatasetRetrievalNodeData
    _retrieval_tool: BaseTool = PrivateAttr(None)

    def __init__(
            self,
            *args: Any,
            flask_app: Flask,
            account_id: UUID,
            **kwargs: Any
    ):
        """构造函数，完成知识库检索节点的初始化"""
        # 1.调用父类构造函数完成数据初始化
        super().__init__(
            *args,
            **kwargs
        )

        # 2.导入依赖注入及检索服务
        from app.http.module import injector
        from internal.service import RetrievalService

        retrieval_service = injector.get(RetrievalService)

        # 3.构建检索服务工具
        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            flask_app=flask_app,
            dataset_ids=self.node_data.dataset_ids,
            account_id=account_id,
            **self.node_data.retrieval_config.dict(),
        )

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """知识库检索节点调用函数，执行相应的知识库检索后返回"""
        # 1.提取检索query输入变量
        # query_input = self.node_data.inputs[0]
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)
        start_at = time.perf_counter()

        # 5.调用知识库检索工具
        combine_documents = self._retrieval_tool.invoke(inputs_dict, config=config)

        # 6.提取并构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

        # 7.返回响应状态
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

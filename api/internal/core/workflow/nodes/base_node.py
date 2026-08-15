#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/1 12:41
@Author     : 歌白
@File       : base_node.py
"""
from abc import ABC

from langchain_core.runnables import RunnableSerializable

from internal.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    """工作流节点基类"""
    node_data: BaseNodeData

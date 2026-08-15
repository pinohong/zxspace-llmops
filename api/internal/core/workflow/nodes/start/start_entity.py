#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/1 12:46
@Author     : 歌白
@File       : start_entity.py
"""

from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    """开始节点数据"""
    inputs: list[VariableEntity] = Field(default_factory=list)  # 开始节点的输入变量信息

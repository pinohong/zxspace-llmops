#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/1 23:43
@Author     : 歌白
@File       : code_entity.py
"""

from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity

# 默认的代码
DefaultCode = """
def main(params):
    return params
"""


class CodeNodeData(BaseNodeData):
    """python代码执行节点数据"""
    code: str = DefaultCode  # 需要执行的Python代码
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=list)  # 输出变量列表

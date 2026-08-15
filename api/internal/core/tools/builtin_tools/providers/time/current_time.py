#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/2 14:13
@Author     : 歌白
@File       : current_time.py
"""
from datetime import datetime
from typing import Any, Type

from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import BaseTool


class CurrentTimeTool(BaseModel):
    """一个用于获取当前时间的工具"""
    name = "current_time"
    description = "一个用于获取当前时间的工具"
    args_schema: Type[BaseModel] = BaseModel

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """获取当前系统的时间并进行格式化反返回"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")


def current_time(**kwargs) -> BaseTool:
    return CurrentTimeTool()

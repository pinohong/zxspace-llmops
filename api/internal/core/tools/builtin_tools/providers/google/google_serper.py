#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/1 17:41
@Author     : 歌白
@File       : google_serper.py
"""

from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool

from internal.lib.helper import add_attribute


class GoogleSerperArgSchema(BaseModel):
    """谷歌SerperAPI搜索参数描述"""
    query: str = Field(description="需要检索查询的语句。")


@add_attribute('args_schema', GoogleSerperArgSchema)
def google_serper(**kwargs) -> BaseTool:
    """谷歌serp搜索"""
    return GoogleSerperRun(
        name="google_serper",
        description="这是一个低成本的谷歌搜索API。当你需要搜索时事的时候，可以使用该工具，该工具的输入是一个查询语句",
        args_schema=GoogleSerperArgSchema,
        api_wrapper=GoogleSerperAPIWrapper()
    )

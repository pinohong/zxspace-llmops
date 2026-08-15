#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/2 14:32
@Author     : 歌白
@File       : wikipedia_search.py
"""
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import BaseTool

from internal.lib.helper import add_attribute


@add_attribute("args_schema", WikipediaAPIWrapper)
def wikipedia_search(**kwargs) -> BaseTool:
    """返回维基百科搜索工具"""
    return WikipediaQueryRun(
        api_wrapper=WikipediaAPIWrapper(),
    )

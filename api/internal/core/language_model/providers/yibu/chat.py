#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/12
@Author     : 歌白
@File       : chat.py
"""
import os
from typing import Tuple

import tiktoken
from langchain_openai.chat_models.base import BaseChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(BaseChatOpenAI, BaseLanguageModel):
    """YIBU中转API聊天模型，OpenAI兼容接口"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            openai_api_key=os.getenv("YIBU_API_KEY"),
            openai_api_base=(os.getenv("YIBU_API_URL") or "https://yibuapi.com/v1").rstrip("/"),
            **kwargs
        )

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """中转模型词表统一使用gpt-4o防止报错"""
        model = "gpt-4o"
        return model, tiktoken.encoding_for_model(model)

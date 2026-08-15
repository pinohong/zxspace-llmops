#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/08/04
@File    : chat.py
"""
import os
from typing import Tuple

import tiktoken
from langchain_openai.chat_models.base import BaseChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(BaseChatOpenAI, BaseLanguageModel):
    """硅基流动(SiliconFlow)聊天模型，OpenAI兼容接口"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            openai_api_key=os.getenv("SILICONFLOW_API_KEY"),
            openai_api_base=(os.getenv("SILICONFLOW_API_BASE") or "https://api.siliconflow.cn/v1").rstrip("/"),
            **kwargs
        )

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """硅基流动的模型没有对应的tiktoken词表，使用gpt-3.5-turbo防止报错"""
        model = "gpt-3.5-turbo"
        return model, tiktoken.encoding_for_model(model)

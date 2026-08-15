#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/5 13:55
@Author     : 歌白
@File       : chat.py.py
"""
from langchain_ollama import ChatOllama

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOllama, BaseLanguageModel):
    """Ollama聊天模型"""
    pass

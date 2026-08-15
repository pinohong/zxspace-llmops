#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/12 13:59
@Author     : 歌白
@File       : embeddings_service.py
"""
import os
from dataclasses import dataclass

import tiktoken
from injector import inject
from langchain.embeddings import CacheBackedEmbeddings
from langchain_community.storage import RedisStore
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from redis import Redis


@inject
@dataclass
class EmbeddingsService:
    """文本嵌入模型（走硅基流动API，OpenAI兼容接口，不再本地加载torch模型）"""
    _store: RedisStore
    _embeddings: Embeddings
    _cache_backed_embeddings: CacheBackedEmbeddings

    def __init__(self, redis: Redis):
        """构造函数，初始化文本嵌入模型客户端，存储器，缓存客户端"""
        self._store = RedisStore(client=redis)
        self._embeddings = OpenAIEmbeddings(
            model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"),
            openai_api_key=os.getenv("SILICONFLOW_API_KEY"),
            openai_api_base=os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1"),
            # 第三方兼容接口无法按模型名本地分词，关闭客户端截断，交给服务端处理
            check_embedding_ctx_length=False,
        )
        self._cache_backed_embeddings = CacheBackedEmbeddings.from_bytes_store(
            self._embeddings,
            self._store,
            namespace="embeddings"
        )

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算传入文本的token数"""
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        return len(encoding.encode(query))

    @property
    def store(self) -> RedisStore:
        """只读属性，安全防护，阻止_store被意外修改"""
        return self._store

    @property
    def embeddings(self) -> Embeddings:
        """只读属性，安全防护，阻止_embeddings被意外修改"""
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> CacheBackedEmbeddings:
        """只读属性，安全防护，阻止_embeddings被意外修改"""
        return self._cache_backed_embeddings

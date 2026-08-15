#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/6/8 23:01
@Author     : 歌白
@File       : vector_database_service.py
"""
from dataclasses import dataclass
from typing import Any

from flask import Flask
from flask_weaviate import FlaskWeaviate
from injector import inject
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_weaviate import WeaviateVectorStore
from weaviate.collections import Collection

from .embeddings_service import EmbeddingsService

COLLECTION_NAME = 'Dataset'


@inject
@dataclass
class VectorDatabaseService:
    """向量数据库服务"""
    # client: WeaviateClient
    # vector_store: WeaviateVectorStore
    embeddings_service: EmbeddingsService
    weaviate: FlaskWeaviate

    async def _get_client(self, flask_app: Flask):
        with flask_app.app_context():
            return self.weaviate.client

    @property
    def vector_store(self) -> WeaviateVectorStore:
        return WeaviateVectorStore(
            client=self.weaviate.client,
            index_name=COLLECTION_NAME,
            text_key="text",
            embedding=self.embeddings_service.cache_backed_embeddings,
        )

    def get_retriever(self) -> VectorStoreRetriever:
        return self.vector_store.as_retriever()

    async def add_documents(self, documents: list[Document], **kwargs: Any):
        """往向量数据库中新增文档，将vector_store使用async进行二次封装，避免在gevent中实现事件循环错误"""
        self.vector_store.add_documents(documents, **kwargs)

    # @classmethod
    # def combine_documents(cls, documents: list[Document]) -> str:
    #     """将对应的文档列表使用换行符进行合并"""
    #     return "\n\n".join([document.page_content for document in documents])

    @property
    def collection(self) -> Collection:
        return self.weaviate.client.collections.get(COLLECTION_NAME)

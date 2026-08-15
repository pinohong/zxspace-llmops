#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/12 12:20
@Author     : 歌白
@File       : default_config.py
"""
# 应用默认配置项
DEFAULT_CONFIG = {
    # wtf配置
    "WTF_CSRF_ENABLED": "False",
    # SQLAlchemy默认配置
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "True",

    # weaviate向量数据库配置
    "WEAVIATE_HTTP_HOST": "localhost",
    "WEAVIATE_HTTP_PORT": 8080,
    "WEAVIATE_GRPC_HOST": "localhost",
    "WEAVIATE_GRPC_PORT": 50051,
    "WEAVIATE_API_KEY": "",

    # Redis数据库配置
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
    "REDIS_USE_SSL": "False",

    # Celery配置
    "CELERY_BROKER_DB": 1,
    "CELERY_RESULT_BACKEND_DB": 1,
    "CELERY_TASK_IGNORE_RESULT": "False",
    "CELERY_RESULT_EXPIRES": 3600,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": "True",
}

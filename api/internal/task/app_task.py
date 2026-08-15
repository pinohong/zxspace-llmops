#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/5 16:01
@Author     : 歌白
@File       : app_task.py
"""
from uuid import UUID

import dotenv
from celery import shared_task

dotenv.load_dotenv()


@shared_task
def auto_create_app(
        name: str,
        description: str,
        account_id: UUID,
) -> None:
    """根据传递的名称、描述、账号id创建一个Agent"""
    from app.http.module import injector
    from internal.service import AppService

    app_service = injector.get(AppService)
    app_service.auto_create_app(name, description, account_id)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/12 20:58
@Author     : 歌白
@File       : my_sqlalchemy.py
"""
from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy as _SQLAlchemy


class SQLAlchemy(_SQLAlchemy):
    """重写Flask-SQLAlchemy中的核心类，实现自动提交"""

    @contextmanager
    def auto_commit(self):
        try:
            yield
            # 提交
            self.session.commit()
        except Exception as e:
            # 如果失败则回滚
            self.session.rollback()
            raise e

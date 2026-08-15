#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/12 00:46
@Author     : 歌白
@File       : conftest.py
"""
import pytest

from app.http.app import app


@pytest.fixture
def client():
    """获取flask应用的测试应用,并返回"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

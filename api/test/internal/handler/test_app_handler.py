#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/12 00:26
@Author     : 歌白
@File       : test_app_handler.py
"""
import pytest

from pkg.response import HttpCode


class TestAppHandler:
    """app控制器的测试类"""

    @pytest.mark.parametrize(
        "app_id, query",
        [
            ("40dfbb13-bc95-4f81-a81b-da6293d3188b", None),
            ("40dfbb13-bc95-4f81-a81b-da6293d3188b", "你好，你是?")
        ]
    )
    def test_completion(self, app_id, query, client):
        resp = client.post(f"/apps/{app_id}/debug", json={"query": query})
        assert resp.status_code == 200
        if query is None:
            assert resp.json.get("code_executor") == HttpCode.VALIDATE_ERROR
        else:
            assert resp.json.get("code_executor") == HttpCode.SUCCESS

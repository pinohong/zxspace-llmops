#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/11 21:18
@Author     : 歌白
@File       : http_code.py
"""
from enum import Enum


class HttpCode(str, Enum):
    SUCCESS = "success"  # 成功的状态
    FAIL = "fail"  # 失败的状态
    NOT_FOUND = "not_found"  # 未找到
    UNAUTHORIZED = "unauthorized"  # 未授权
    FORBIDDEN = "forbidden"  # 无权限
    # VALIDATE_ERROR = "validate_error"  # 数据验证
    VALIDATE_ERROR = "VALIDATE_ERROR"  # 数据验证

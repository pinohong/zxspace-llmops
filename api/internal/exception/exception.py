#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/11 22:37
@Author     : 歌白
@File       : exception.py
"""
from dataclasses import field
from typing import Any

from pkg.response import HttpCode


class CustomException(Exception):
    code: HttpCode = HttpCode.FAIL
    message: str = ""
    data: Any = field()

    def __init__(self, message: str = "", data: Any = None):
        super().__init__()
        self.message = message
        self.data = data


class FailException(CustomException):
    """通用失败异常"""
    pass


class NotFoundException(CustomException):
    """未找到数据异常"""
    code: HttpCode = HttpCode.NOT_FOUND


class UnauthorizedException(CustomException):
    """未授权异常"""
    code: HttpCode = HttpCode.UNAUTHORIZED


class ForbiddenException(CustomException):
    """无权限异常"""
    code: HttpCode = HttpCode.FORBIDDEN


class ValidateErrorException(CustomException):
    """数据校验异常"""
    code: HttpCode = HttpCode.VALIDATE_ERROR

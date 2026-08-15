#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/5/11 21:24
@Author     : 歌白
@File       : response.py
"""
from dataclasses import field, dataclass
from typing import Any, Union, Generator

from flask import jsonify, stream_with_context, Response as FlaskResponse

from .http_code import HttpCode


@dataclass
class Response:
    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: Any = field(default_factory=dict)


def json(data: Response = None):
    response = jsonify(data)
    # response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    # response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    # response.headers["Access-Control-Allow-Methods"] = "GET,POST"
    # response.headers["Access-Control-Allow-Credentials"] = "true"
    return response, 200


def success_json(data: Any = None):
    """成功的数据响应"""
    return json(Response(code=HttpCode.SUCCESS, message="", data=data))


def fail_json(data: Any = None):
    """失败的数据响应"""
    return json(Response(code=HttpCode.FAIL, message="", data=data))


def validate_error_json(errors: dict = None):
    """数据验证错误响应"""
    first_key = next(iter(errors))
    if first_key is not None:
        msg = errors.get(first_key)[0]
    else:
        msg = ""
    return json(Response(code=HttpCode.VALIDATE_ERROR, message=msg, data=errors))


def message(code: HttpCode = None, msg: str = ""):
    """基础的消息响应 ,固定返回消息提示,数据固定为空字典"""
    return json(Response(code=code, message=msg))


def success_message(msg: str = ""):
    """成功的消息响应"""
    return message(HttpCode.SUCCESS, msg=msg)


def fail_message(msg: str = ""):
    """成功的消息响应"""
    return message(HttpCode.FAIL, msg=msg)


def not_find_message(msg: str = ""):
    """没找到的消息响应"""
    return message(HttpCode.NOT_FOUND, msg=msg)


def unauthorized_message(msg: str = ""):
    """未授权的消息响应"""
    return message(HttpCode.UNAUTHORIZED, msg=msg)


def forbidden_message(msg: str = ""):
    """未授权的消息响应"""
    return message(HttpCode.FORBIDDEN, msg=msg)


def compact_generate_response(response: Union[Response, Generator]) -> FlaskResponse:
    """统一合并处理块输出以及流式事件输出"""
    # 1.检测下是否为块输出(Response)
    if isinstance(response, Response):
        return json(response)
    else:
        # 2.response格式为生成器，代表本次响应需要执行流式事件输出
        def generate() -> Generator:
            """构建generate函数，流式从response中获取数据"""
            yield from response

        # 3.返回携带上下文的流式事件输出
        return FlaskResponse(
            stream_with_context(generate()),
            status=200,
            mimetype="text/event-stream",
        )

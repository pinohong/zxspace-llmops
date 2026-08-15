#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/21 22:29
@Author     : 歌白
@File       : auth_schema.py
"""

from flask_wtf import FlaskForm
from marshmallow import fields, Schema
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length, regexp

from pkg.password import password_pattern


class PasswordLoginReq(FlaskForm):
    """账号密码登录请求结构"""
    email = StringField("email", validators=[
        DataRequired("登录邮箱不能为空"),
        Email("登录邮箱格式错误"),
        Length(min=5, max=254, message="登录邮箱长度在5-254个字符")
    ])

    password = StringField("password", validators=[
        DataRequired("账号密码不能为空"),
        regexp(regex=password_pattern, message="密码必须是数字密码组合，并且长度为8-16")
    ])


class PasswordLoginResp(Schema):
    """账号密码授权认证响应结构"""
    access_token = fields.String()
    expire_at = fields.Integer()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/21 22:16
@Author     : 歌白
@File       : auth_handler.py
"""
from dataclasses import dataclass

from flask_login import logout_user
from injector import inject

from internal.schema.auth_schema import PasswordLoginReq, PasswordLoginResp
from pkg.response import success_message,success_json,validate_error_json
from internal.service import AccountService


@inject
@dataclass
class AuthHandler:
    """LLMOps平台自有授权认证处理器"""
    account_service:AccountService
    def password_login(self):
        """账号密码登录"""
        # 1.提取请求并校验数据
        req = PasswordLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务登录账号
        credential = self.account_service.password_login(req.email.data,req.password.data)

        # 3.创建响应结构并返回
        resp = PasswordLoginResp()
        return success_json(resp.dump(credential))

    def logout(self):
        """退出登录,用于提示前端清除授权凭证"""
        # login_required
        logout_user()
        return success_message("退出登录成功")

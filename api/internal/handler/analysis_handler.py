#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/8/6 21:36
@Author     : 歌白
@File       : analysis_service.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask_login import login_required, current_user
from injector import inject

from internal.service import AnalysisService
from pkg.response import success_json


@inject
@dataclass
class AnalysisHandler:
    """统计分析处理器"""
    analysis_service: AnalysisService

    @login_required
    def get_app_analysis(self, app_id: UUID):
        """更具传递的应用id获取应用的统计信息"""
        app_analysis = self.analysis_service.get_app_analysis(app_id, current_user)
        return success_json(app_analysis)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/21 14:31
@Author     : 歌白
@File       : __init__.py.py
"""
from .github_oauth import GithubOAuth
from .oauth import OAuth

__all__ = ["GithubOAuth", "OAuth"]

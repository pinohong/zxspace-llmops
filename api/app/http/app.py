#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/4/2 17:38
@Author     : 歌白
@File       : app.py
"""

# 为开发环境配置猴子补丁
# import os
# if os.environ.get("FLASK_DEBUG") == "0" or os.environ.get("FLASK_ENV") == "production":
#     from gevent import monkey
#
#     monkey.patch_all()
#
#     import grpc.experimental.gevent
#
#     grpc.experimental.gevent.init_gevent()

import dotenv
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_weaviate import FlaskWeaviate

from config import Config
from internal.middleware import Middleware
from internal.router import Router
from internal.server import Http
from pkg.my_sqlalchemy import SQLAlchemy
from .module import injector

dotenv.load_dotenv()
conf = Config()

# 将.env变量加载到环境中
app = Http(
    __name__,
    conf=conf,
    db=injector.get(SQLAlchemy),
    weaviate=injector.get(FlaskWeaviate),
    migrate=injector.get(Migrate),
    login_manager=injector.get(LoginManager),
    middleware=injector.get(Middleware),
    router=injector.get(Router)
)
# with app.app_context():
#     for rule in app.url_map.iter_rules():
#         print(f"{rule.method} {rule}")
celery = app.extensions["celery"]

if __name__ == "__main__":
    app.run(debug=True)

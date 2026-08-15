#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/4/2 16:56
@Author     : 歌白
@File       : test.py
"""
import weaviate

client = weaviate.connect_to_local(host="127.0.0.1", port=8080)
client.collections.delete("Dataset")
client.close()
print("残缺Dataset已删除")

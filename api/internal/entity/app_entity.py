#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/19 16:45
@Author     : 歌白
@File       : app_entity.py
"""
from enum import Enum

# 生成icon描述提示词模板
GENERATE_ICON_PROMPT_TEMPLATE = """你是一个拥有10年经验的AI绘画工程师，可以将用户传递的`应用名称`和`应用描述`转换为对应应用的icon描述。
该描述主要用于DallE AI绘画，并且该描述是英文，用户传递的数据如下:

应用名称: {name}。
应用描述: {description}。

并且除了icon描述提示词外，其他什么都不要生成"""


class AppStatus(str, Enum):
    """应用状态枚举类"""
    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """应用配置类型枚举类"""
    DRAFT = "draft"
    PUBLISHED = "published"


# 应用默认配置信息
DEFAULT_APP_CONFIG = {
    "model_config": {  # 模型配置
        "provider": "deepseek",  # 模型供应商
        "model": "deepseek-v4-pro",  # 模型名称
        "parameters": {  # 模型参数
            "temperature": 0.5,  # 温度
            "top_p": 0.85,  # Top P采样
            "frequency_penalty": 0.2,  # 频率惩罚
            "presence_penalty": 0.2,  # 存在惩罚
            "max_tokens": 8192,  # 最大Token数
        },
    },
    "dialog_round": 3,  # 携带上下文轮数
    "preset_prompt": "",  # 预设提示词
    "tools": [],  # 应用关联工具列表
    "workflows": [],  # 应用关联工作流列表
    "datasets": [],  # 应用关联知识库列表
    "retrieval_config": {  # 检索配置
        "retrieval_strategy": "semantic",  # 检索策略
        "k": 10,  # 检索返回条数
        "score": 0.5,  # 检索匹配度阈值
    },
    "long_term_memory": {  # 长期记忆配置
        "enable": False,  # 是否启用
    },
    "opening_statement": "",  # 开场白文案
    "opening_questions": [],  # 开场白建议问题列表
    "speech_to_text": {  # 语音转文本配置
        "enable": False,  # 是否启用
    },
    "text_to_speech": {  # 文本转语音配置
        "enable": False,  # 是否启用
        "voice": "alex",  # 音色
        "auto_play": False,  # 是否自动播放
    },
    "suggested_after_answer": {  # 回答后生成建议问题
        "enable": True,  # 是否启用
    },
    "review_config": {  # 审核配置
        "enable": False,  # 是否启用
        "keywords": [],  # 关键词列表
        "inputs_config": {  # 输入审核配置
            "enable": False,  # 是否启用
            "preset_response": "",  # 预设回复
        },
        "outputs_config": {  # 输出审核配置
            "enable": False,  # 是否启用
        },
    },
}

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/17 22:38
@Author     : 歌白
@File       : conversation_entity.py
"""
from enum import Enum

SUMMARIZER_TEMPLATE = """逐步总结提供的对话内容，在之前的总结基础上继续添加并返回一个新的总结，并确保新总结的长度不要超过2000个字符，必要的时候可以删除一些信息，尽可能简洁。

EXAMPLE
当前总结:
人类询问 AI 对人工智能的看法。AI 认为人工智能是一股向善的力量。

新的会话:
Human: 为什么你认为人工智能是一股向善的力量？
AI: 因为人工智能将帮助人类发挥他们全部的潜力。

新的总结:
人类询问AI对人工智能的看法，AI认为人工智能是一股向善的力量，因为它将帮助人类发挥全部潜力。
END OF EXAMPLE

当前总结:
{summary}

新的会话:
{new_lines}

新的总结:"""

# 会话名字提示模板
CONVERSATION_NAME_TEMPLATE = """你是对话标题提取助手。
根据用户输入内容提炼唯一核心对话主题名，遵守以下规则：
1. 忽略寒暄、语气词、无意义铺垫，只保留核心诉求/讨论议题；
2. 输出为2–7字简短标题，不用问句、长句、标点；
3. 仅输出主题名称，不要解释、不要分点、不要额外文字。"""

from pydantic import BaseModel, Field


class ConversationInfo(BaseModel):
    """
    任务：解析用户输入文本，输出标准化语言判定、推理、简短话题总结
    通用语种判定枚举（language_type仅允许填写以下固定值，不可自定义描述）：
    - 纯中文 / 纯英文 / 纯日语 / 纯法语 / 纯韩语 / 多语种混合
    语种输出强制规则：
    1. subject、reasoning 必须与文本表意主体语言保持一致，禁止中英混杂；
    2. 混合文本判定标准：外文仅URL、零散单词，核心语义为中文则统一中文输出；反之以外文输出；
    输出约束：
    1. reasoning：一句话简短说明语种判断理由，禁止冗余长文；
    2. subject：融合话题+用户意图精简概括，2~20个字，简洁直白；
    3. 仅输出标准JSON，不要附加多余文字、注释、换行。

    示例1：
    用户输入: hi, my name is LiHua.
    {
        "language_type": "纯英文",
        "reasoning": "全文均为英文，无中文内容，输出使用英文",
        "subject": "Introduce myself to AI"
    }

    示例2：
    用户输入: www.imooc.com讲了什么
    {
        "language_type": "多语种混合",
        "reasoning": "仅网址为英文，核心提问是中文，全部字段使用中文",
        "subject": "查询慕课网站讲解内容"
    }
    """
    language_type: str = Field(
        description="语种分类，仅能填写固定选项：纯中文 / 纯英文 / 纯日语 / 纯法语 / 纯韩语 / 多语种混合"
    )
    reasoning: str = Field(
        description="语种判断推理过程，一句话简短说明，文字语种和subject保持统一"
    )
    subject: str = Field(
        description="融合对话主题与用户意图的简短概括，2~20字，语种与输入主体语言一致，简洁易懂"
    )


SUGGESTED_QUESTIONS_TEMPLATE = """
# 生成候选提问任务
## 权重优先级（最高强制）
优先围绕用户最新一轮发言生成问题，历史上下文仅作为辅助补充，不得本末倒置。
## 生成规范
1. 总量固定输出3个问题；
2. 单条字符上限50字，口语化贴合用户提问习惯；
3. 三类角度各一条，避免同质化：
   - 追问类：深挖当前话题细节
   - 拓展类：延伸相关关联内容
   - 求证类：确认模糊信息、边界条件
4. 严禁：复制用户已提出的原话、脱离对话的无关问题、重复语义问题；
## 输出格式
只返回纯JSON字符串数组，格式示例：["问题1","问题2","问题3"]
不输出任何额外文字、注释、思考步骤、换行说明。
"""


class SuggestedQuestions(BaseModel):
    """预测用户后续潜在提问，严格输出长度、数量、格式合规的问题数组"""
    questions: list[str] = Field(
        description="长度为3的字符串列表，每条问题不超过50字符；分别为追问、拓展、求证三类不同角度，无重复语义"
    )


class InvokeFrom(str, Enum):
    """会话调用来源"""
    SERVICE_API = "service_api"  # 开发API服务调用
    WEB_APP = "web_app"  # web应用
    DEBUGGER = "debugger"  # 调试页面
    ASSISTANT_AGENT = "assistant_agent"  # 辅助Agent调用


class MessageStatus(str, Enum):
    """会话状态"""
    NORMAL = "normal"  # 正常
    STOP = "stop"  # 停止
    TIMEOUT = "timeout"  # 超时
    ERROR = "error"  # 出错

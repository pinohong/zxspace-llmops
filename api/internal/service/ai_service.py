#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/28 18:27
@Author     : 歌白
@File       : ai_service.py
"""
import json
from dataclasses import dataclass
from typing import Generator
from uuid import UUID

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.exception import ForbiddenException
from internal.model import Account, Message
from pkg.my_sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService


@inject
@dataclass
class AIService(BaseService):
    db: SQLAlchemy
    conversation_service: ConversationService

    def optimize_prompt(self):
        pass

    def generate_suggested_questions_from_message_id(self, message_id: UUID, account: Account) -> list[str]:
        """根据传递的消息id_账号生成建议问题列表"""
        # 1.查询消息并校验权限信息
        message = self.get(Message, message_id)
        if not message or message.created_by != account.id:
            raise ForbiddenException("该条消息不存在或无权限")
        # 2.构建对话历史列表
        histories = f"Human: {message.query}\nAI: {message.answer}"

        # 3.调用服务生成的建议问题
        return self.conversation_service.generate_suggested_questions(histories)

    @classmethod
    def optimize_prompt(cls, prompt: str) -> Generator[str, None, None]:
        """根据传递的prompt进行优化生成"""
        # 1.构建优化prompt的提示词模版
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "{prompt}"),
        ])

        # 2.构建LLM
        llm = ChatOpenAI(
            model="deepseek-v4-pro",
            temperature=0.5,
            extra_body={"thinking": {"type": "disabled"}},
        )

        # 3.组装优化连
        optimize_chain = prompt_template | llm | StrOutputParser()

        # 4.调用链并流式事件返回
        for optimize_prompt in optimize_chain.stream({"prompt": prompt}):
            # 5.组装响应数据
            data = {"optimize_prompt": optimize_prompt}
            yield f"event: optimize_prompt\ndata: {json.dumps(data)}\n\n"

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/19 12:17
@Author     : 歌白
@File       : queue_entity.py
@Desc       : 智能体队列通信实体定义
             Agent 在执行过程中通过内存队列将推理过程实时推送给调用方（前端），
             本模块定义了队列中传输的事件枚举和数据结构。
             通信方式：Agent（后台线程）→ Queue → AgentQueueManager.listen() → SSE → 前端
"""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from internal.entity.conversation_entity import MessageStatus


class QueueEvent(str, Enum):
    """
    Agent 执行过程中产生的事件类型枚举
    这些事件通过 AgentQueueManager 的队列实时推送给调用方实现流式展示
    """
    LONG_TERM_MEMORY_RECALL = "long_term_memory_recall"  # 长期记忆召回：Agent 拉取了历史对话摘要
    AGENT_THOUGHT = "agent_thought"  # Agent 推理：LLM 决定调用哪个工具及参数
    AGENT_MESSAGE = "agent_message"  # Agent 消息：LLM 逐 token 生成的文本回答
    AGENT_ACTION = "agent_action"  # Agent 动作：工具执行完毕返回结果
    DATASET_RETRIEVAL = "dataset_retrieval"  # 知识库检索：从关联知识库中召回相关文档
    AGENT_END = "agent_end"  # Agent 正常完成：所有步骤执行完毕
    STOP = "stop"  # 用户主动停止：外部通过 Redis 发送了停止信号
    ERROR = "error"  # Agent 内部错误：LLM 调用或工具执行异常
    TIMEOUT = "timeout"  # Agent 超时：整体执行时间超过 600 秒
    PING = "ping"  # 心跳：每 10 秒发送一次，用于保持 SSE 连接


class AgentThought(BaseModel):
    """
    Agent 单步推理的完整数据载体
    每个 AgentThought 对应一次"思考→行动→观察"循环中的一个环节，
    由后台线程生产，前端通过 SSE 逐条消费
    """
    # ── 标识 ──
    id: UUID  # 事件唯一 ID，同一轮 LLM 调用的多个 token 流共享一个 id
    task_id: UUID  # 本次会话任务的全局唯一 ID，用于关联整次对话

    # ── 事件类型与推理内容 ──
    event: QueueEvent  # 当前事件属于哪一类型（决定前端如何展示）
    thought: str = ""  # LLM 推理/思考过程，可能是工具调用计划（AGENT_THOUGHT）或逐 token 输出（AGENT_MESSAGE）
    observation: str = ""  # 观察结果，如工具返回数据或长期记忆召回内容

    # ── 工具调用信息 ──
    tool: str = ""  # 被调用的工具名称，仅在 AGENT_ACTION 事件中有值
    tool_input: dict = Field(default_factory=dict)  # 调用工具时传入的参数字典

    # ── LLM 消息与计费 ──
    message: list[dict] = Field(default_factory=dict)  # 本次推理使用的完整消息列表（用于后续存储到 DB）
    message_token_count: int = 0  # 输入消息消耗的 token 数
    message_unit_price: float = 0  # 输入 token 单价
    message_price_unit: float = 0  # 输入 token 价格单位

    # ── 回答与计费 ──
    answer: str = ""  # LLM 生成的最终答案文本（AGENT_MESSAGE 事件中逐 token 累加）
    answer_token_count: int = 0  # 输出 token 数
    answer_unit_price: float = 0  # 输出 token 单价
    answer_price_unit: float = 0  # 输出 token 价格单位

    # ── 汇总统计 ──
    total_token_count: int = 0  # 本次调用总 token 消耗
    total_price: float = 0  # 本次调用总费用
    latency: float = 0  # 本次推理耗时（秒），从 LLM 开始调用到当前 token 生成


class AgentResult(BaseModel):
    """智能体推理观察最终结构"""
    query: str = ""  # 原始提问
    image_urls: list[str] = Field(default_factory=list)  # 用户的图片输入列表

    message: list[dict] = Field(default_factory=list)  # 产生最终答案的消息列表
    message_token_count: int = 0  # 消息花费的token数
    message_unit_price: float = 0  # 单价
    message_price_unit: float = 0  # 价格单位

    answer: str = ""  # Agent产生的最终答案
    answer_token_count: int = 0  # LLM生成答案的token数
    answer_unit_price: float = 0  # 单价
    answer_price_unit: float = 0  # 价格单位

    total_token_count: int = 0  # 总token消耗数量
    total_price: float = 0  # 总价格
    latency: float = 0  # 总耗时

    status: str = MessageStatus.NORMAL  # 消息的状态
    error: str = ""  # 错误消息

    agent_thoughts: list[AgentThought] = Field(default_factory=list)  # 产生答案的推理步骤

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/18 21:04
@Author     : 歌白
@File       : base_agent.py
@Desc       : Agent 抽象基类
             所有 Agent 实现（FunctionCallAgent、未来的 ReActAgent 等）均继承此类。
             核心设计：将 LangGraph 编译后的图放到后台线程执行，主线程通过
             AgentQueueManager 队列接收实时事件，实现 SSE 流式推送给前端。
             继承关系：BaseAgent → LangChain Serializable + Runnable
"""
import uuid
from abc import abstractmethod
from threading import Thread
from typing import Optional, Any, Iterator

from langchain_core.load import Serializable
from langchain_core.pydantic_v1 import PrivateAttr
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import AgentConfig, AgentState
from internal.core.agent.entities.queue_entity import (
    AgentResult,
    AgentThought,
    QueueEvent,
)
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.exception import FailException
from .agent_queue_manager import AgentQueueManager


class BaseAgent(Serializable, Runnable):
    """
    LLMOps 项目 Agent 抽象基类

    设计要点：
    - 继承 LangChain 的 Serializable + Runnable，无缝融入 LangChain 生态
    - _build_agent() 由子类实现，返回编译后的 LangGraph 图
    - stream() 方法将图放到后台线程执行，通过队列管理器向外推送 AgentThought 事件
    - invoke() 预留为块内容响应（当前为桩），用于非流式场景
    """
    # ── 公开字段 ──
    llm: BaseLanguageModel  # LLM 大语言模型实例（ChatOpenAI 等）
    agent_config: AgentConfig  # Agent 运行时配置（工具列表、提示词、审核规则等）

    # ── 私有字段 ──
    _agent: CompiledStateGraph = PrivateAttr(None)  # 编译后的 LangGraph 图（子类 _build_agent 注入）
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)  # 队列管理器（用于流式通信）

    class Config:
        arbitrary_types_allowed = True  # 允许使用非标准 Pydantic 类型（如 LangChain 的 LLM 实例）

    def __init__(
            self,
            llm: BaseLanguageModel,
            agent_config: AgentConfig,
            *args,
            **kwargs,
    ):
        """初始化 Agent：构建图结构程序并创建队列管理器"""
        super().__init__(*args, llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()  # 调用子类实现的图构建方法
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_from=agent_config.invoke_from,
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """
        构建 LangGraph 图结构（抽象方法，由子类实现）

        子类需要定义图的节点、边和条件分支，最终返回 graph.compile()
        例如 FunctionCallAgent 实现了: preset_operation → memory_recall → llm ⇄ tools → end
        """
        raise NotImplementedError("_build_agent()未实现")

    def invoke(self, input: AgentState, config: Optional[RunnableConfig] = None) -> AgentResult:
        """块内容响应，一次性生成完整内容后返回"""
        # 1.调用stream方法获取流式事件输出数据
        content = input["messages"][0].content
        query = ""
        image_urls = []
        if isinstance(content, str):
            query = content
        elif isinstance(content, list):
            query = content[0]["text"]
            image_urls = [chunk["image_url"]["url"] for chunk in content if chunk.get("type") == "image_url"]
        agent_result = AgentResult(query=query, image_urls=image_urls)
        agent_thoughts = {}
        for agent_thought in self.stream(input, config):
            # 2.提取事件id并转换成字符串
            event_id = str(agent_thought.id)

            # 3.除了ping事件，其他事件全部记录
            if agent_thought.event != QueueEvent.PING:
                # 4.单独处理agent_message事件，因为该事件为数据叠加
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    # 5.检测是否已存储了事件
                    if event_id not in agent_thoughts:
                        # 6.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 7.叠加智能体消息事件
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency,
                        })
                    # 8.更新智能体消息答案
                    agent_result.answer += agent_thought.answer
                else:
                    # 9.处理其他类型的智能体事件，类型均为覆盖
                    agent_thoughts[event_id] = agent_thought

                    # 10.单独判断是否为异常消息类型，如果是则修改状态并记录错误
                    if agent_thought.event in [QueueEvent.STOP, QueueEvent.TIMEOUT, QueueEvent.ERROR]:
                        agent_result.status = agent_thought.event
                        agent_result.error = agent_thought.observation if agent_thought.event == QueueEvent.ERROR else ""

        # 11.将推理字典转换成列表并存储
        agent_result.agent_thoughts = [agent_thought for agent_thought in agent_thoughts.values()]

        # 12.完善message
        agent_result.message = next(
            (agent_thought.message for agent_thought in agent_thoughts.values()
             if agent_thought.event == QueueEvent.AGENT_MESSAGE),
            []
        )

        # 13.更新总耗时
        agent_result.latency = sum([agent_thought.latency for agent_thought in agent_thoughts.values()])

        return agent_result

    def stream(
            self,
            input: AgentState,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> Iterator[AgentThought]:
        """
        流式输出模式：将 Agent 执行过程以 SSE 事件流方式实时推送

        执行流程：
        1. 初始化 state 中的 task_id、history、iteration_count
        2. 创建后台线程运行 self._agent.invoke(input)（LangGraph 执行）
        3. 主线程通过 AgentQueueManager.listen() 持续消费队列事件并 yield
        4. 前端通过 SSE 逐条接收 AgentThought 事件并渲染

        线程模型：
        ┌─────────── 后台线程 ───────────┐     ┌───── 队列 ─────┐     ┌─── 主线程（SSE）───┐
        │ LangGraph.invoke(state)        │ ──→ │ Queue.put()    │ ──→ │ listen() → yield │ → 前端
        │ 各节点 publish AgentThought    │     │ in-memory dict │     │ 超时/停止检测    │
        └────────────────────────────────┘     └────────────────┘     └──────────────────┘
        """
        # 1.校验子类是否已构建 Agent
        if not self._agent:
            raise FailException("智能体未成功构建，请核实后尝试")

        # 2.初始化 state 字段（未传入则使用默认值）
        input["task_id"] = input.get("task_id", uuid.uuid4())
        input["history"] = input.get("history", [])
        input["iteration_count"] = input.get("iteration_count", 0)

        import threading
        print(f"[DEBUG] === stream start, task_id={input['task_id']} ===")
        print(f"[DEBUG] active threads: {len(threading.enumerate())}")
        for t in threading.enumerate():
            print(f"  - {t.name} alive={t.is_alive()} daemon={t.daemon}")

        def run_agent():
            try:
                print(f"[DEBUG] run_agent: invoke start")
                self._agent.invoke(input)
                print(f"[DEBUG] run_agent: invoke done")
            finally:
                print(f"[DEBUG] run_agent: finally -> stop_listen")
                self._agent_queue_manager.stop_listen(input["task_id"])

        # 3.LangGraph 图放到后台线程执行，避免阻塞主线程
        thread = Thread(target=run_agent)
        thread.start()

        # 4.主线程通过队列管理器监听并 yield 事件，实现流式输出
        yield from self._agent_queue_manager.listen(input["task_id"])

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        """只读属性，返回 Agent 关联的队列管理器实例"""
        return self._agent_queue_manager

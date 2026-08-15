#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/18 21:41
@Author     : 歌白
@File       : function_call_agent.py
"""

import json
import logging
import re
import time
import uuid
from typing import Literal

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    RemoveMessage,
    ToolMessage,
    messages_to_dict,
    AIMessage,
)
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import (
    AgentState,
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    DATASET_RETRIEVAL_TOOL_NAME,
    MAX_ITERATION_RESPONSE,
    AgentConfig,
)
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.exception import FailException
from .base_agent import BaseAgent


class FunctionCallAgent(BaseAgent):
    """基于 Function Calling（工具调用）模式的 Agent"""

    def __init__(self, llm: BaseLanguageModel, agent_config: AgentConfig, *args, **kwargs):
        super().__init__(llm=llm, agent_config=agent_config, *args, **kwargs)

    def _build_agent(self) -> CompiledStateGraph:
        """
        构建 LangGraph 函数调用 Agent 图
        """
        # 1.创建以 AgentState 为状态类型的图
        graph = StateGraph(AgentState)

        # 2.注册四个节点：预设操作、长期记忆、LLM、工具
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3.编排边和条件跳转
        graph.set_entry_point("preset_operation")  # 入口
        graph.add_conditional_edges(
            "preset_operation",
            self._preset_operation_condition
        )  # 审核条件：通过 → memory，命中 → END
        graph.add_edge("long_term_memory_recall", "llm")  # 记忆完成后直接进入 LLM
        graph.add_conditional_edges(
            "llm",
            self._tools_condition
        )  # LLM 后：需要工具 → tools，否则 → END
        graph.add_edge("tools", "llm")  # 工具执行后回到 LLM（循环）

        # 4.编译为可执行的图对象
        return graph.compile()

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """
        预设操作节点：执行输入内容审核
        """
        # 1.获取审核配置与用户输入
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        # 2.判断是否需要输入审核
        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])
            if contains_keyword:
                # 3.命中敏感词 → 推送预设响应 + 结束事件
                preset_response = review_config["inputs_config"]["preset_response"]
                print(f"[DEBUG] keyword matched! preset_response={preset_response}")

                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=preset_response,
                    message=messages_to_dict(state["messages"]),
                    answer=preset_response,
                    latency=0,
                ))
                print(f"[DEBUG] published AGENT_MESSAGE, task_id={state['task_id']}")
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END,
                ))
                print(f"[DEBUG] published AGENT_END")
                # 返回 AIMessage 作为终止标记（condition 中通过 type=="ai" 识别）
                return {"messages": [AIMessage(preset_response)]}

        # 4.通过审核 → 空消息，不影响现有消息列表
        return {"messages": []}

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """长期记忆召回节点：组装系统提示词 + 历史消息 + 当前用户输入"""
        # 1.根据配置决定是否注入长期记忆
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                observation=long_term_memory,
            ))

        # 2.构建系统消息（注入预设提示词和长期记忆）
        preset_messages = [
            SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                preset_prompt=self.agent_config.preset_prompt,
                long_term_memory=long_term_memory,
            ))
        ]

        # 3.拼接短期记忆（历史消息对）
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4.校验历史消息必须是偶数条（Human + AI 成对出现）
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "智能体历史消息列表格式错误")
                logging.exception(
                    f"智能体历史消息列表格式错误，len(history)={len(history)}，"
                    f"history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("智能体历史消息列表格式错误")
            preset_messages.extend(history)

        # 5.提取当前用户消息
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 6.用组装好的消息替换 state 中的原始消息
        #    RemoveMessage 用于从 state 中移除旧的用户消息，避免重复
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """LLM 推理节点：流式调用大语言模型"""
        # 1.迭代次数保护：超过上限则终止
        if state["iteration_count"] > self.agent_config.max_iteration_count:
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE,
                thought=MAX_ITERATION_RESPONSE,
                message=messages_to_dict(state["messages"]),
                answer=MAX_ITERATION_RESPONSE,
                latency=0,
            ))
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END,
            ))
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        # 2.获取 LLM 实例并根据配置绑定工具
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm
        if (
                ModelFeature.TOOL_CALL in llm.features
                and hasattr(llm, "bind_tools")
                and callable(getattr(llm, "bind_tools"))
                and len(self.agent_config.tools) > 0
        ):
            llm = llm.bind_tools(self.agent_config.tools)

        # 3.流式调用 LLM，逐 chunk 处理
        gathered = None  # 累积完整消息（用于最终返回）
        is_first_chunk = True  # 标记是否第一个 chunk（用于初始化 gathered）
        try:
            for chunk in llm.stream(state["messages"]):
                # 累积完整消息
                if is_first_chunk:
                    gathered = chunk
                    is_first_chunk = False
                else:
                    gathered += chunk

                # 4.文本内容逐 token 推送 AGENT_MESSAGE 事件。
                #    注意：不能仅凭首个 chunk 判断生成类型。DeepSeek 思考模式下模型
                #    可能先输出一段文本、再在同一响应中携带 tool_calls，若提前判定为
                #    "message"，会导致工具调用被忽略、并提前推送 AGENT_END 截断 SSE 流。
                if chunk.content:
                    review_config = self.agent_config.review_config
                    content = chunk.content
                    # 输出审核：敏感词替换为 **
                    if review_config["enable"] and review_config["outputs_config"]["enable"]:
                        for keyword in review_config["keywords"]:
                            content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)

                    self.agent_queue_manager.publish(state["task_id"], AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=content,
                        message=messages_to_dict(state["messages"]),
                        answer=content,
                        latency=(time.perf_counter() - start_at),
                    ))

        except Exception as e:
            logging.exception(f"LLM节点发生错误，错误信息：{str(e)}")
            self.agent_queue_manager.publish_error(state["task_id"], f"LLM节点发生错误，错误信息：{str(e)}")
            raise e

        # 5.根据完整消息确定生成类型：携带 tool_calls 则视为工具调用（thought），
        #    否则视为直接回答（message）。不能仅凭首个 chunk 判断，原因见上方注释。
        generation_type = "thought" if (gathered and gathered.tool_calls) else "message"

        # 8.计算LLM的输入+输出token总数
        input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
        output_token_count = self.llm.get_num_tokens_from_messages([gathered])

        # 9.获取输入/输出价格和单位
        input_price, output_price, unit = self.llm.get_pricing()

        # 10.计算总token+总成本
        total_token_count = input_token_count + output_token_count
        total_price = (input_token_count * input_price + output_token_count * output_price) * unit

        # 11.流式调用完成后，根据生成类型做收尾处理
        if generation_type == "thought":
            # 工具调用模式：推送 AGENT_THOUGHT（工具名称 + 参数的 JSON），然后进入 tools 节点
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT,
                thought=json.dumps(gathered.tool_calls),
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                # 答案相关字段
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # Agent推理统计相关
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
        elif generation_type == "message":
            # 7.如果LLM直接生成answer则表示已经拿到了最终答案，推送一条空内容用于计算总token+总成本，并停止监听
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE,
                thought="",
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                # 答案相关字段
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # Agent推理统计相关
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            # 直接回答模式：推送 AGENT_END，Agent 流程结束
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END,
            ))
        # if hasattr(gathered, "tool_calls") and gathered.tool_calls:
        #     self.agent_queue_manager.publish(state["task_id"], AgentThought(
        #         id=id,
        #         task_id=state["task_id"],
        #         event=QueueEvent.AGENT_THOUGHT,
        #         thought=json.dumps(gathered.tool_calls),
        #         message=messages_to_dict(state["messages"]),
        #         latency=(time.perf_counter() - start_at),
        #     ))
        # else:
        #     self.agent_queue_manager.publish(state["task_id"], AgentThought(
        #         id=uuid.uuid4(),
        #         task_id=state["task_id"],
        #         event=QueueEvent.AGENT_END,
        #     ))

        return {
            "messages": [gathered],
            "iteration_count": state["iteration_count"] + 1
        }

    def _tools_node(self, state: AgentState) -> AgentState:
        """工具执行节点：调用 LLM 选择的工具并返回结果"""
        # 1.构建工具名 → 工具实例的映射表
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 2.提取 LLM 最后一条消息中的 tools_calls
        tool_calls = state["messages"][-1].tool_calls

        # 3.遍历执行每个工具调用
        messages = []
        for tool_call in tool_calls:
            id = uuid.uuid4()
            start_at = time.perf_counter()

            try:
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])
            except Exception as e:
                tool_result = f"工具执行出错：{str(e)}"

            # 4.将工具执行结果包装为 ToolMessage
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(tool_result),
                name=tool_call["name"],
            ))

            # 5.根据工具类型推送不同事件
            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL
            )
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=event,
                observation=json.dumps(tool_result),
                tool=tool_call["name"],
                tool_input=tool_call["args"],
                latency=(time.perf_counter() - start_at),
            ))

        return {"messages": messages}

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """条件边：判断 LLM 输出后是否需要执行工具"""
        messages = state["messages"]
        ai_message = messages[-1]
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal[
        "long_term_memory_recall", "__end__"]:
        """条件边：预设操作后判断是否继续"""
        message = state["messages"][-1]
        if message.type == "ai":
            return END
        return "long_term_memory_recall"

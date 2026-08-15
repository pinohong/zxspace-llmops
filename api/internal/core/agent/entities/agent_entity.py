#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/18 21:16
@Author     : 歌白
@File       : agent_entity.py
@Desc       : Agent 配置、状态与提示词定义
             本模块是 Agent 系统的"配置中心"，包含：
               1. Agent 系统提示词模板（注入预设提示词和长期记忆）
               2. AgentConfig  —— 前端编排后传入的运行时配置
               3. AgentState   —— LangGraph 图中流转的状态对象
               4. 常量定义（工具名称、错误提示等）
"""
from uuid import UUID

from langchain_core.messages import AnyMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState

from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom

# ──────────────────────────────────────────────────────────────
# Agent 系统预设提示词模板
# 占位符 {preset_prompt} 由前端编排时填写（用户自定义人设/任务）
# 占位符 {long_term_memory} 由长期记忆召回节点动态注入（历史对话摘要）
# ──────────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT_TEMPLATE = """你是一个高度定制的智能体应用，旨在为用户提供准确、专业的内容生成和问题解答，请严格遵守以下规则：

1.**预设任务执行**
  - 你需要基于用户提供的预设提示(PRESET-PROMPT)，按照要求生成特定内容，确保输出符合用户的预期和指引；

2.**工具调用和参数生成**
  - 当任务需要时，你可以调用绑定的外部工具(如知识库检索、计算工具等)，并生成符合任务需求的调用参数，确保工具使用的准确性和高效性；

3.**历史对话和长期记忆**
  - 你可以参考`历史对话`记录，结合经过摘要提取的`长期记忆`，以提供更加个性化和上下文相关的回复，这将有助于在连续对话中保持一致性，并提供更加精确的反馈；

4.**外部信息获取**
  - 如果用户的问题超出当前的知识范围或需要额外补充，你可以根据需要选择合适的搜索工具（如网络搜索、知识库检索等）获取信息，确保答案的完整性和正确性；

5.**高效性和简洁性**
  - 保持对用户需求的精准理解和高效响应，提供简洁且有效的答案，避免冗长或无关信息；

<预设提示>
{preset_prompt}
</预设提示>

<长期记忆>
{long_term_memory}
</长期记忆>
"""

# 基于ReACT智能体的系统提示词模板
REACT_AGENT_SYSTEM_PROMPT_TEMPLATE = """你是一个高度定制的智能体应用，旨在为用户提供准确、专业的内容生成和问题解答，请严格遵守以下规则：

1.**预设任务执行**
  - 你需要基于用户提供的预设提示(PRESET-PROMPT)，按照要求生成特定内容，确保输出符合用户的预期和指引；

2.**工具调用和参数生成**
  - 当任务需要时，你可以调用绑定的外部工具(如知识库检索、计算工具等)，并生成符合任务需求的调用参数，确保工具使用的准确性和高效性，如果不需要调用工具的时候，请不要返回任何工具调用相关的json信息，如果用户传递了多条消息，请不要在最终答案里重复生成工具调用参数；

3.**历史对话和长期记忆**
  - 你可以参考`历史对话`记录，结合经过摘要提取的`长期记忆`，以提供更加个性化和上下文相关的回复，这将有助于在连续对话中保持一致性，并提供更加精确的反馈；

4.**外部知识库检索**
  - 如果用户的问题超出当前的知识范围或需要额外补充，你可以调用`recall_dataset(知识库检索工具)`以获取外部信息，确保答案的完整性和正确性；

5.**高效性和简洁性**
  - 保持对用户需求的精准理解和高效响应，提供简洁且有效的答案，避免冗长或无关信息；

6.**工具调用**
  - Agent智能体应用还提供了工具调用，具体信息可以参考<工具描述>里的工具信息，工具调用参数请参考`args`中的信息描述。
  - 工具描述说明:
    - 示例: google_serper - 这是一个低成本的谷歌搜索API。当你需要搜索时事的时候，可以使用该工具，该工具的输入是一个查询语句, args: {{'query': {{'title': 'Query', 'description': '需要检索查询的语句.', 'type': 'string'}}}}
    - 格式: 工具名称 - 工具描述, args: 工具参数信息字典
  - LLM生成的工具调用参数说明:
    - 示例: ```json\n{{"name": "google_serper", "args": {{"query": "慕课网 AI课程"}}}}\n```
    - 格式: ```json\n{{"name": 需要调用的工具名称, "args": 调用该工具的输入参数字典}}\n```
    - 要求:
      - 生成的内容必须是符合规范的json字符串，并且仅包含两个字段`name`和`args`，其中`name`代表工具的名称，`args`代表调用该工具传递的参数，如果没有参数则传递空字典`{{}}`。
      - 生成的内容必须以"```json"为开头，以"```"为结尾，前面和后面不要添加任何内容，避免代码解析出错。
      - 注意`工具描述参数args`和最终生成的`工具调用参数args`的区别，不要错误生成。
      - 如果不需要工具调用，则正常生成即可，程序会自动检测内容开头是否为"```json"进行判断
    - 正确示例:
      - ```json\\n{{"name": "google_serper", "args": {{"query": "慕课网 AI课程"}}}}\\n```
      - ```json\\n{{"name": "current_time", "args": {{}}}}\\n```
      - ```json\\n{{"name": "dalle", "args": {{"query": "一幅老爷爷爬山的图片", "size": "1024x1024"}}}}\\n```
    - 错误示例:
      - 错误原因(在最前的```json前生成了内容): 好的，我将调用工具进行搜索。\\n```json\\n{{"name": "google_serper", "args": {{"query": "慕课网 AI课程"}}}}\\n```
      - 错误原因(在最后的```后生成了内容): ```json\\n{{"name": "google_serper", "args": {{"query": "慕课网 AI课程"}}}}\\n```，我将准备调用工具，请稍等。
      - 错误原因(生成了json，但是不包含在"```json"和"```"内): {{"name": "current_time", "args": {{}}}}
      - 错误原因(将描述参数的内容填充到生成参数中): ```json\\n{{"name": "google_serper", "args": {{"query": {{'title': 'Query', 'description': '需要检索查询的语句.', 'type': 'string'}}}}\n```

<预设提示>
{preset_prompt}
</预设提示>

<长期记忆>
{long_term_memory}
</长期记忆>

<工具描述>
{tool_description}
</工具描述>"""


class AgentConfig(BaseModel):
    """
    Agent 运行时配置，由前端编排面板传入
    包含 LLM 选择、工具绑定、记忆策略、审核规则等全部可配置项
    通过 app_service 从草稿配置中提取数据后构造此对象
    """
    # ── 用户与调用来源 ──
    user_id: UUID  # 操作用户/终端用户的唯一标识
    invoke_from: InvokeFrom = InvokeFrom.WEB_APP  # 调用来源：web_app / debugger / service_api

    # ── 迭代控制 ──
    max_iteration_count: int = 5  # LLM 最大迭代次数，防止无限 tool-call 循环

    # ── 提示词 ──
    system_prompt: str = AGENT_SYSTEM_PROMPT_TEMPLATE  # 系统级提示词，包含预设提示与长期记忆占位符
    preset_prompt: str = ""  # 用户自定义的预设提示词，由前端编排时填写，运行时注入到 system_prompt 中

    # ── 长期记忆 ──
    enable_long_term_memory: bool = False  # 是否启用长期记忆（历史对话摘要），开启后每次对话会更新摘要

    # ── 工具 ──
    tools: list[BaseTool] = Field(default_factory=list)  # 绑定的 LangChain 工具列表，LLM 可从中选择调用

    # ── 审核 ──
    review_config: dict = Field(
        default_factory=lambda: DEFAULT_APP_CONFIG["review_config"]
    )  # 内容审核配置，包含敏感词列表和输入/输出审核开关


class AgentState(MessagesState):
    """
    LangGraph 图中流转的状态对象（扩展自 MessagesState）
    每个节点读写此对象，实现有状态的工作流编排

    MessagesState 内置 messages: list[AnyMessage] 字段，无需重复声明
    """
    task_id: UUID  # 本次会话任务的唯一 ID，每次流式调用生成一个新的
    iteration_count: int  # LLM 调用迭代次数计数器，从 0 开始，每轮 +1
    history: list[AnyMessage]  # 短期记忆：最近的 [Human, AI, Human, AI...] 消息对
    long_term_memory: str  # 长期记忆：历史对话的累积摘要文本


# ──────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────

DATASET_RETRIEVAL_TOOL_NAME = "dataset_retrieval"
"""知识库检索工具的固定名称，用于区分工具事件类型（AGENT_ACTION vs DATASET_RETRIEVAL）"""

MAX_ITERATION_RESPONSE = "当前Agent迭代次数已经超过限制，请重试"
"""超过最大迭代次数时返回给用户的提示信息，同时发送 AGENT_END 事件终止流程"""

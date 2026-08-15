# Agent 智能体模块架构说明

## 目录结构

```
internal/core/agent/
├── __init__.py
├── agents/
│   ├── __init__.py              # 对外导出 BaseAgent / FunctionCallAgent / AgentQueueManager
│   ├── base_agent.py            # Agent 抽象基类（继承 LangChain Runnable）
│   ├── agent_queue_manager.py   # 内存队列管理器（后台线程 → 主线程通信）
│   └── function_call_agent.py   # Function Calling Agent 实现（当前唯一 Agent）
├── entities/
│   ├── __init__.py
│   ├── agent_entity.py          # AgentConfig / AgentState / 系统提示词模板
│   └── queue_entity.py          # QueueEvent 枚举 / AgentThought 数据模型
└── README.md                    # 本文件
```

---

## 各文件职责

### `entities/agent_entity.py` — Agent 配置中心

| 组件 | 说明 |
|------|------|
| `AGENT_SYSTEM_PROMPT_TEMPLATE` | 系统提示词模板，包含 `{preset_prompt}` 和 `{long_term_memory}` 占位符 |
| `AgentConfig` | 前端编排传入的运行时配置（LLM、工具列表、审核规则、记忆开关等） |
| `AgentState` | LangGraph 图流转的状态对象，包含 messages、task_id、history、long_term_memory |

### `entities/queue_entity.py` — 队列通信实体

| 组件 | 说明 |
|------|------|
| `QueueEvent` | 事件枚举：AGENT_MESSAGE、AGENT_THOUGHT、AGENT_ACTION 等 11 种事件类型 |
| `AgentThought` | 单次推理的数据载体（包含 token、工具调用、耗时等信息），通过队列传递 |

### `agents/base_agent.py` — Agent 抽象基类

核心设计：

```
BaseAgent (Serializable + Runnable)
  ├── _build_agent()          ← 抽象方法，子类实现 LangGraph 图构建
  ├── stream(input)           ← 流式入口：后台线程跑图 → 主线程 yield 事件
  └── invoke(input)           ← 块响应入口（预留）
```

**线程模型**：LangGraph 图在**后台线程**执行（各节点向队列 publish 事件），主线程通过 `AgentQueueManager.listen()` 消费队列 → 经 SSE 推送给前端。

### `agents/agent_queue_manager.py` — 队列管理器

```
           后台线程（Agent 各节点）              主线程（SSE）
          ┌─────────────────────┐         ┌──────────────────┐
          │ publish(event)      │ ──→     │ listen(task_id)  │
          │ → Queue.put()       │ 内存队列 │ → Queue.get()    │
          │                     │ Task A   │ → yield event    │
          │                     │ Task B   │ → SSE → 前端     │
          └─────────────────────┘         └──────────────────┘
```

**关键机制**：
- 每个 `task_id` 对应一个独立的 `Queue`，避免多用户混淆
- Redis 用于跨请求通信（停止信号检测、任务归属标记）
- 超时保护：600s 自动发送 TIMEOUT 事件
- 心跳保活：每 10s 发送 PING 事件，防止 SSE 连接断开
- 终止类型事件（STOP/ERROR/TIMEOUT/AGENT_END）会自动向队列插入 None 哨兵

### `agents/function_call_agent.py` — Function Calling Agent

当前 LLMOps 唯一的 Agent 实现，基于 LangGraph StateGraph 构建：

```
                    ┌──────────────────────┐
                    │  preset_operation    │  ← 输入审核节点
                    │  (敏感词检测)         │
                    └──────┬───────────────┘
                           │ [通过]                [命中敏感词] → END
                           ↓
                    ┌──────────────────────┐
                    │ long_term_memory     │  ← 长期记忆召回节点
                    │ _recall              │     (注入历史摘要)
                    └──────┬───────────────┘
                           ↓
                    ┌──────────────────────┐
                    │        llm           │  ← LLM 推理节点
                    │  (流式 token 输出)    │     (工具绑定 + 输出审核)
                    └──────┬───────────────┘
                           │ [需要工具]           [不需要工具] → END
                           ↓
                    ┌──────────────────────┐
                    │       tools          │  ← 工具执行节点
                    │  (调用 LangChain 工具) │     → 回 llm（循环）
                    └──────────────────────┘
```

---

## 为什么这样设计？

### 1. 线程分离（交互不阻塞）

LangGraph 的 `graph.invoke()` 是同步阻塞的。如果直接在主线程执行，整个 Flask 请求会卡住直到 Agent 完成，前端无法实时看到推理过程。

**解决方案**：将图放到后台线程执行，主线程通过队列消费中间事件 → SSE 流式推送给前端。

### 2. 内存队列 + Redis 混合通信

- **内存队列**：低延迟，适合高频实时事件推送（LLM 每个 token 都是一次 push）
- **Redis**：跨请求通信，适合低频控制信号（用户点击"停止"按钮时，由另一个 API 请求写入 Redis key，Agent 的 listen 循环轮询检测）

### 3. 观察者模式（解耦 Agent 与前端）

Agent 各节点通过 `AgentQueueManager.publish()` 发布事件，完全不知道前端是 SSE 还是 WebSocket。调用方通过 `listen()` 生成器消费即可，前端协议可随时替换。

### 4. LangGraph 状态机（可扩展性）

`BaseAgent._build_agent()` 返回 `CompiledStateGraph`，子类可自由定义图的节点和边。例如未来可以实现 `ReActAgent`、`PlanAndExecuteAgent` 等不同策略，只需新建一个子类实现 `_build_agent()` 即可，队列管理和流式输出逻辑无需改动。

### 5. 单一入口点

前端只需调用一次 `POST /apps/{id}/conversations`，即可获得完整的 SSE 事件流，覆盖从输入审核 → 记忆召回 → LLM推理 → 工具执行 → 终止的全部事件。无需轮询或多次请求。

---

## 核心数据流

```
app_service.debug_chat()
  │
  ├─ 1. 创建 Message（存 DB）
  ├─ 2. 获取 draft_app_config → 构造 AgentConfig
  ├─ 3. 创建 FunctionCallAgent(agent_config, queue_manager)
  ├─ 4. 调用 agent.run(query, history, summary)
  │       │
  │       └─→ BaseAgent.stream(state)
  │             ├─ 后台线程: langgraph.invoke(state)
  │             │     ├─ preset_operation    → publish AGENT_MESSAGE / AGENT_END
  │             │     ├─ memory_recall       → publish LONG_TERM_MEMORY_RECALL
  │             │     ├─ llm                 → publish AGENT_MESSAGE（逐token）
  │             │     │                         publish AGENT_THOUGHT（工具调用）
  │             │     ├─ tools               → publish AGENT_ACTION / DATASET_RETRIEVAL
  │             │     └─ llm ... 循环         → publish AGENT_END
  │             │
  │             └─ 主线程: queue_manager.listen(task_id)
  │                   └─ yield AgentThought → SSE → 前端
  │
  ├─ 5. 收尾：保存 MessageAgentThought + 更新 Message + 更新 Conversation
  │       ├─ summary()          → 更新长期记忆
  │       └─ generate_conversation_name() → 首次对话生成名称
  └─ 6. 通道关闭
```

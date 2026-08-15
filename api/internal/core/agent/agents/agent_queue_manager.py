#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/19 12:27
@Author     : 歌白
@File       : agent_queue_manager.py
@Desc       : 智能体队列管理器
             Agent 的后台线程在 LangGraph 各节点中调用 publish() 生产事件，
             主线程通过 listen() 生成器消费事件 → 经 SSE 推送给前端。

             核心数据结构：
             _queues: dict[str, Queue]    —— 以 task_id 为 key 的内存队列字典
             Redis:   用于跨请求通信（停止信号、任务归属）

             生命周期：
             1. stream() 调用 → 创建后台线程 → 启动 _agent.invoke()
             2. 后台线程在各节点 publish 事件 → 写入对应 task_id 的 Queue
             3. listen() 循环从 Queue 中 get 事件 → yield 给调用方
             4. 遇到 STOP/ERROR/TIMEOUT/AGENT_END 或超时 600s → 停止监听
"""
import queue
import time
import uuid
from queue import Queue
from typing import Generator
from uuid import UUID

from redis import Redis

from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """
    智能体队列管理器

    职责：
    - 创建/管理每个 task 的内存队列
    - 提供 publish() 接口供 Agent 节点写入事件
    - 提供 listen() 接口供主线程消费事件（生成器模式）
    - 通过 Redis 实现跨请求的停止信号检测
    - 超时保护（600s）+ 心跳保活（每 10s 发送 PING）
    """
    user_id: UUID  # 发起请求的用户 ID
    invoke_from: InvokeFrom  # 调用来源（决定 Redis key 前缀）
    redis_client: Redis  # Redis 客户端实例（通过依赖注入获取）
    _queues: dict[str, Queue]  # task_id → Queue 的内存映射，key 为 str(task_id)

    def __init__(
            self,
            user_id: UUID,
            invoke_from: InvokeFrom,
    ) -> None:
        """构造函数，初始化队列管理器的内存结构和 Redis 客户端"""
        self.user_id = user_id
        self.invoke_from = invoke_from
        self._queues = {}

        # 延迟导入注入器，避免循环依赖（此模块被 agents 导入，而 injector 在 app 层）
        from app.http.module import injector
        self.redis_client = injector.get(Redis)

    def listen(self, task_id: UUID) -> Generator:
        """监听指定任务队列，以生成器方式持续 yield 事件"""
        listen_timeout = 600  # 最大监听时长（秒）
        start_time = time.time()  # 监听开始时间
        last_ping_time = 0  # 上次 PING 的 10s 间隔计数

        while True:
            elapsed_time = time.time() - start_time

            # 超时保护：超过 600s 自动终止
            if elapsed_time >= listen_timeout:
                self.publish(task_id, AgentThought(
                    id=uuid.uuid4(),
                    task_id=task_id,
                    event=QueueEvent.TIMEOUT,
                ))

            # 外部停止信号检测（用户在前端点击停止按钮时，通过 API 在 Redis 中设置标记）
            if self._is_stopped(task_id):
                self.publish(task_id, AgentThought(
                    id=uuid.uuid4(),
                    task_id=task_id,
                    event=QueueEvent.STOP,
                ))

            # PING 直接 yield，不经过队列，避免自产自消导致 None 哨兵被淹没
            if elapsed_time // 10 > last_ping_time:
                yield AgentThought(
                    id=uuid.uuid4(),
                    task_id=task_id,
                    event=QueueEvent.PING,
                )
                last_ping_time = elapsed_time // 10

            try:
                item = self.queue(task_id).get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue

    def _listen(self, task_id: UUID) -> Generator:
        """
        监听指定任务队列，以生成器方式持续 yield 事件

        工作机制：
        - 循环从队列中 get 事件（1s 超时防止空转）
        - 每 10s 通过队列 self-publish 一个 PING 心跳事件
        - 超过 600s 自动发布 TIMEOUT 事件并退出
        - 检测到 Redis 中的停止信号时发布 STOP 事件并退出

        Yields:
            AgentThought —— 单个 Agent 事件，由调用方通过 SSE 发送给前端
        """
        # 超时控制变量
        listen_timeout = 600  # 最大监听时长（秒）
        start_time = time.time()  # 监听开始时间
        last_ping_time = 0  # 上次 PING 的 10s 间隔计数

        while True:
            try:
                # 从队列中取事件，timeout=1s 防止永久阻塞
                item = self.queue(task_id).get(timeout=1)
                print(f"[DEBUG] listen got: {type(item).__name__} is None={item is None}")
                # None 是终止信号（由 stop_listen 或 AGENT_END 等事件触发）
                if item is None:
                    break
                yield item
            except queue.Empty:  # 1s 内无事件，继续循环
                continue
            finally:
                elapsed_time = time.time() - start_time

                # 心跳：每 10 秒发送一次 PING，保持 SSE 连接活跃
                if elapsed_time // 10 > last_ping_time:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.PING,
                    ))
                    last_ping_time = elapsed_time // 10

                # 超时保护：超过 600s 自动终止
                if elapsed_time >= listen_timeout:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.TIMEOUT,
                    ))

                # 外部停止信号检测（用户在前端点击停止按钮时，通过 API 在 Redis 中设置标记）
                if self._is_stopped(task_id):
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.STOP,
                    ))

    def stop_listen(self, task_id: UUID) -> None:
        """
        停止监听：向队列末尾塞入 None 作为终止哨兵
        前台 listen() 循环收到 None 后退出 while 循环
        """
        print(f"[DEBUG] stop_listen called, task_id={task_id}")
        self.queue(task_id).put(None)
        print(f"[DEBUG] stop_listen: None put to queue")

    def publish(self, task_id: UUID, Agent_Thought: AgentThought) -> None:
        """
        发布事件到指定任务队列
        Agent 后端的各个 LangGraph 节点通过此方法推送事件

        如果事件类型属于终止类型（STOP/ERROR/TIMEOUT/AGENT_END），
        会自动调用 stop_listen 插入终止哨兵
        """
        # 1.将事件放入队列
        self.queue(task_id).put(Agent_Thought)

        # 2.终止类事件 → 额外插入 None 哨兵，让 listen 退出循环
        if Agent_Thought.event in [
            QueueEvent.STOP,
            QueueEvent.ERROR,
            QueueEvent.TIMEOUT,
            QueueEvent.AGENT_END,
        ]:
            self.stop_listen(task_id)

    def publish_error(self, task_id: UUID, error) -> None:
        """便捷方法：发布一个 ERROR 事件到队列"""
        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=QueueEvent.ERROR,
            observation=str(error),
        ))

    def _is_stopped(self, task_id: UUID) -> bool:
        """
        检测外部是否发出了停止信号
        机制：前端点击停止按钮 → API 在 Redis 中 SET key → 此处 GET 检测
        """
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        result = self.redis_client.get(task_stopped_cache_key)
        return result is not None

    @classmethod
    def set_stop_flag(cls, task_id: UUID, invoke_from: InvokeFrom, user_id: UUID) -> None:
        """根据传递的任务id+调用来源停止某次会话"""
        # 1.获取redis_client客户端
        from app.http.module import injector
        redis_client = injector.get(Redis)

        # 2.获取当前任务的缓存键,如果任务没执行,则不需要停止
        result = redis_client.get(cls.generate_task_belong_cache_key(task_id))
        if not result:
            return

        # 3.计算对应缓存键的结果
        user_prefix = "account" if invoke_from in [
            InvokeFrom.WEB_APP, invoke_from.DEBUGGER,
            InvokeFrom.ASSISTANT_AGENT,
        ] else "end-user"

        # 4.生成停止键标识
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        redis_client.setex(stopped_cache_key, 600, 1)

    def queue(self, task_id: UUID) -> Queue:
        """
        获取或创建指定 task_id 的内存队列
        若队列不存在则创建新的 Queue 并写入 Redis 任务归属标记
        """
        q = self._queues.get(str(task_id))
        if not q:
            # 根据调用来源确定 Redis key 前缀（区分账号用户和终端用户）
            user_prefix = "account" if self.invoke_from in [
                InvokeFrom.WEB_APP,
                InvokeFrom.DEBUGGER,
                InvokeFrom.ASSISTANT_AGENT,
            ] else "end-user"

            # 在 Redis 中写入任务归属标记，用于后续权限校验或跨请求关联
            self.redis_client.setex(
                self.generate_task_belong_cache_key(task_id),
                1800,  # 30 分钟过期
                f"{user_prefix}-{str(self.user_id)}",
            )

            q = Queue()
            self._queues[str(task_id)] = q

        return q

    # ── Redis 键名生成器（类方法，便于外部也在同一套命名约定下操作）──

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """生成任务归属缓存键：用于记录某个 task 属于哪个用户"""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """生成任务停止信号缓存键：前端停止时写入，listen 轮询时检测"""
        return f"generate_task_stopped:{str(task_id)}"

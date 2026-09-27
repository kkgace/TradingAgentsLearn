# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""进程内 SSE 事件总线：topic -> [(订阅者事件循环, 队列), ...]。

每个订阅者在 subscribe 时记录自己所在的事件循环；publish 可从任意线程调用，
把事件投递到各订阅者自己的循环里（call_soon_threadsafe），互不干扰——
不存在全局"绑定循环"，也就不存在被后启动线程覆盖、事件投进无人运行的循环的竞态。
"""
import asyncio
import json
import threading
from typing import Any


class SSEBus:
    def __init__(self):
        # topic -> [(loop, queue), ...]
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: Any):
        """任意线程调用：把事件投给 topic 的所有订阅者（投到各自的循环）"""
        with self._lock:
            subs = list(self._subs.get(topic, []))
        if not subs:
            return
        data = json.dumps(payload, ensure_ascii=False, default=str)
        for loop, q in subs:
            def _put(q=q, data=data):
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    pass  # 慢消费者：丢弃本条，由前端按 seq 补全（详情接口可重放）
            try:
                loop.call_soon_threadsafe(_put)
            except RuntimeError:
                pass  # 该订阅者的循环已关闭（连接断开），忽略

    async def subscribe(self, topic: str):
        """订阅 topic（须在事件循环内调用）；断开时自动清理注册项"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subs.setdefault(topic, []).append((loop, q))
        try:
            while True:
                data = await q.get()
                yield data
        finally:
            with self._lock:
                lst = self._subs.get(topic, [])
                if (loop, q) in lst:
                    lst.remove((loop, q))
                if not lst:
                    self._subs.pop(topic, None)


bus = SSEBus()

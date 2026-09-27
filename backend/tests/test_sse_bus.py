# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""SSE 总线测试：跨线程投递到订阅者各自的循环、无订阅者安全、断开自动清理"""
import asyncio
import json
import threading
import time

from app.services.sse_bus import SSEBus


def _run_subscriber(bus: SSEBus, topic: str, out: list, n: int):
    """在独立线程的事件循环里消费 n 条后退出"""
    async def _main():
        async for data in bus.subscribe(topic):
            out.append(data)
            if len(out) >= n:
                break
    asyncio.run(_main())


def _wait_registered(bus: SSEBus, topic: str, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with bus._lock:
            if bus._subs.get(topic):
                return True
        time.sleep(0.01)
    return False


def test_publish_from_other_thread_reaches_subscriber():
    bus = SSEBus()
    out: list[str] = []
    t = threading.Thread(target=_run_subscriber, args=(bus, "analysis:1", out, 2),
                         daemon=True)
    t.start()
    assert _wait_registered(bus, "analysis:1")

    # 主线程发布（模拟分析后台线程），事件应投递到订阅者线程的循环
    bus.publish("analysis:1", {"type": "agent", "seq": 1, "agent": "market"})
    bus.publish("analysis:1", {"type": "done", "analysis_id": 1})
    t.join(timeout=3)
    assert not t.is_alive()
    assert [json.loads(x) for x in out] == [
        {"type": "agent", "seq": 1, "agent": "market"},
        {"type": "done", "analysis_id": 1},
    ]


def test_publish_without_subscribers_is_noop():
    bus = SSEBus()
    bus.publish("triggers", {"anything": 1})        # 不抛异常
    with bus._lock:
        assert bus._subs == {}


def test_subscriber_cleanup_on_disconnect():
    bus = SSEBus()
    out: list[str] = []
    t = threading.Thread(target=_run_subscriber, args=(bus, "t", out, 1),
                         daemon=True)
    t.start()
    assert _wait_registered(bus, "t")
    bus.publish("t", {"x": 1})
    t.join(timeout=3)
    # 生成器正常退出 -> finally 清理注册项
    deadline = time.time() + 2
    while time.time() < deadline:
        with bus._lock:
            if not bus._subs.get("t"):
                break
        time.sleep(0.01)
    with bus._lock:
        assert "t" not in bus._subs


def test_two_subscribers_both_receive():
    bus = SSEBus()
    out1: list[str] = []
    out2: list[str] = []
    t1 = threading.Thread(target=_run_subscriber, args=(bus, "t", out1, 1), daemon=True)
    t2 = threading.Thread(target=_run_subscriber, args=(bus, "t", out2, 1), daemon=True)
    t1.start()
    t2.start()
    assert _wait_registered(bus, "t")
    with bus._lock:
        while len(bus._subs["t"]) < 2:
            time.sleep(0.01)

    bus.publish("t", {"hello": "世界"})
    t1.join(timeout=3)
    t2.join(timeout=3)
    assert json.loads(out1[0]) == {"hello": "世界"}
    assert json.loads(out2[0]) == {"hello": "世界"}

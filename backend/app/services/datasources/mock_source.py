# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""内置确定性 Mock 数据源：20 只示例股票（CN/HK/US 混合），离线可用。

价格带时间确定性漂移：以锚定价为中心 ±4% 内按 30 秒一档缓慢波动（双 sin 合成，
无随机数），保证同档位结果可复现、跨档位有变化——触发器 price_above/price_below
因此能被真实演示，而非"要么立即命中要么永不命中"。"""
import math
import time
from datetime import datetime, timezone

from .base import DataSourceBase

# 确定性示例数据（锚定价固定，行情价在锚点附近漂移，保证演示与测试可复现）
_MOCK_STOCKS: list[dict] = [
    # ---- A 股 CN ----
    {"code": "600519", "name": "贵州茅台", "market": "CN", "industry": "白酒", "currency": "CNY", "pe": 22.5, "pb": 8.6, "price": 1620.00},
    {"code": "000001", "name": "平安银行", "market": "CN", "industry": "银行", "currency": "CNY", "pe": 4.8, "pb": 0.55, "price": 11.35},
    {"code": "300750", "name": "宁德时代", "market": "CN", "industry": "电池", "currency": "CNY", "pe": 21.3, "pb": 4.9, "price": 185.60},
    {"code": "601318", "name": "中国平安", "market": "CN", "industry": "保险", "currency": "CNY", "pe": 7.2, "pb": 0.85, "price": 48.20},
    {"code": "600036", "name": "招商银行", "market": "CN", "industry": "银行", "currency": "CNY", "pe": 5.9, "pb": 0.92, "price": 33.45},
    {"code": "002594", "name": "比亚迪", "market": "CN", "industry": "汽车", "currency": "CNY", "pe": 18.6, "pb": 4.1, "price": 245.80},
    {"code": "000858", "name": "五粮液", "market": "CN", "industry": "白酒", "currency": "CNY", "pe": 16.4, "pb": 3.8, "price": 128.90},
    {"code": "601899", "name": "紫金矿业", "market": "CN", "industry": "有色金属", "currency": "CNY", "pe": 12.5, "pb": 3.2, "price": 18.75},
    {"code": "600276", "name": "恒瑞医药", "market": "CN", "industry": "医药", "currency": "CNY", "pe": 45.2, "pb": 5.6, "price": 46.30},
    {"code": "000651", "name": "格力电器", "market": "CN", "industry": "家电", "currency": "CNY", "pe": 8.1, "pb": 1.9, "price": 40.55},
    # ---- 港股 HK ----
    {"code": "00700", "name": "腾讯控股", "market": "HK", "industry": "互联网", "currency": "HKD", "pe": 17.8, "pb": 3.4, "price": 385.20},
    {"code": "09988", "name": "阿里巴巴-W", "market": "HK", "industry": "互联网", "currency": "HKD", "pe": 14.2, "pb": 1.6, "price": 82.40},
    {"code": "03690", "name": "美团-W", "market": "HK", "industry": "本地生活", "currency": "HKD", "pe": 22.0, "pb": 4.8, "price": 118.60},
    {"code": "01810", "name": "小米集团-W", "market": "HK", "industry": "消费电子", "currency": "HKD", "pe": 21.5, "pb": 2.9, "price": 27.85},
    {"code": "00939", "name": "建设银行", "market": "HK", "industry": "银行", "currency": "HKD", "pe": 4.1, "pb": 0.45, "price": 6.12},
    # ---- 美股 US ----
    {"code": "AAPL", "name": "苹果", "market": "US", "industry": "消费电子", "currency": "USD", "pe": 28.5, "pb": 38.0, "price": 228.50},
    {"code": "MSFT", "name": "微软", "market": "US", "industry": "软件", "currency": "USD", "pe": 33.2, "pb": 12.1, "price": 425.30},
    {"code": "NVDA", "name": "英伟达", "market": "US", "industry": "半导体", "currency": "USD", "pe": 55.6, "pb": 42.5, "price": 118.90},
    {"code": "TSLA", "name": "特斯拉", "market": "US", "industry": "汽车", "currency": "USD", "pe": 62.4, "pb": 9.8, "price": 248.00},
    {"code": "GOOGL", "name": "谷歌A", "market": "US", "industry": "互联网", "currency": "USD", "pe": 21.9, "pb": 6.3, "price": 165.40},
]


def _drift_price(base: float, code: str, now: float | None = None) -> float:
    """锚定价 ±4.2% 内的确定性漂移：30 秒一档，三 sin 合成，同档同价、可复现。
    三个频率不公约的分量保证相邻档位几乎总有可感知变化（演示触发器用）。"""
    t = int(now if now is not None else time.time()) // 30
    seed = sum(ord(c) for c in code)              # 稳定种子（hash() 跨进程不稳定，禁用）
    wave = (0.025 * math.sin(t / 7.0 + seed)
            + 0.012 * math.sin(t / 2.3 + seed * 1.7)
            + 0.005 * math.sin(t / 1.13 + seed * 2.3))
    return round(base * (1 + wave), 2)


def _with_drift(row: dict, now: float | None = None) -> dict:
    """复制行并把 price 替换为当前档位的漂移价（不修改原锚定数据）"""
    out = dict(row)
    out["price"] = _drift_price(float(row["price"]), row["code"], now)
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out


class MockDataSource(DataSourceBase):
    """确定性 Mock 数据源实现"""
    name = "mock"

    def list_stocks(self) -> list[dict]:
        return [self.get_quote(s["code"]) or dict(s) for s in _MOCK_STOCKS]

    def get_quote(self, code: str) -> dict | None:
        code = (code or "").strip()
        for s in _MOCK_STOCKS:
            if s["code"] == code:
                return _with_drift(s)
        return None

    def search(self, q: str, market: str | None = None) -> list[dict]:
        q = (q or "").strip().lower()
        market = (market or "").strip().upper() or None
        out = []
        for s in _MOCK_STOCKS:
            if market and s["market"] != market:
                continue
            if not q or q in s["code"].lower() or q in s["name"].lower():
                out.append(_with_drift(s))
        return out

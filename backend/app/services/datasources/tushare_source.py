# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""Tushare 数据源：A 股日线行情（Tushare Pro 官方 HTTP API，无需 tushare SDK）。

- 接口：POST {TUSHARE_API}，body {"api_name","token","params","fields"}
- 数据：stock_basic（代码表）、trade_cal（交易日历）、daily_basic（收盘价/PE/PB）
- 行情为**日频收盘数据**（tushare 免费档为日线），盘内不会跳动
- 覆盖范围：A 股完整支持；港股/美股与查询失败的代码回退 Mock 数据（每代码仅告警一次）
- 缓存：代码表 1h / 最新交易日 5min / 日线快照与单码行情 30s，均线程安全
"""
import logging
import threading
import time
from datetime import datetime, timedelta

import httpx

from app.core.config import settings
from .base import DataSourceBase
from .mock_source import MockDataSource, _MOCK_STOCKS

logger = logging.getLogger(__name__)


class TushareAPIError(RuntimeError):
    """Tushare 接口返回非 0 code 或网络失败"""


class _TTLCache:
    """线程安全的简单 TTL 缓存"""

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            exp, val = self._data.get(key, (None, None))
            if exp is not None and exp > time.time():
                return val
            return None

    def set(self, key, value, ttl: float):
        with self._lock:
            self._data[key] = (time.time() + ttl, value)


# 交易所后缀映射：6/9 开头沪市、0/2/3 开头深市、4/8/9(北交) 开头京市
_TS_SUFFIX = (
    ("68", "SH"), ("60", "SH"), ("90", "SH"),
    ("00", "SZ"), ("30", "SZ"), ("20", "SZ"),
    ("43", "BJ"), ("83", "BJ"), ("87", "BJ"), ("88", "BJ"), ("92", "BJ"),
)


def to_ts_code(code: str) -> str | None:
    """6 位 A 股代码 -> tushare ts_code（600519 -> 600519.SH）；非 6 位数字返回 None"""
    code = (code or "").strip()
    if len(code) == 6 and code.isdigit():
        for prefix, suffix in _TS_SUFFIX:
            if code.startswith(prefix):
                return f"{code}.{suffix}"
    return None


class TushareSource(DataSourceBase):
    name = "tushare"

    def __init__(self, token: str | None = None, api: str | None = None,
                 universe: list[str] | None = None):
        self._token = token or settings.TUSHARE_TOKEN
        self._api = (api or settings.TUSHARE_API).strip()
        self._universe = universe or [c.strip() for c in settings.TUSHARE_CODES.split(",")
                                      if c.strip()]
        self._cache = _TTLCache()
        self._warned: set[str] = set()      # 已告警代码，避免轮询刷日志
        self._mock: MockDataSource | None = None

    # ---------------- 底层请求 ----------------

    def _request(self, api_name: str, params: dict, fields: str) -> list[dict]:
        """调 Tushare Pro HTTP 接口，返回 list[dict]（fields 作 key）；失败抛 TushareAPIError"""
        try:
            r = httpx.post(self._api, json={"api_name": api_name, "token": self._token,
                                            "params": params, "fields": fields},
                           timeout=max(3, settings.TUSHARE_TIMEOUT))
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            raise TushareAPIError(f"{api_name} 请求失败：{e}") from e
        if body.get("code") != 0:
            raise TushareAPIError(f"{api_name} 返回错误：code={body.get('code')} msg={body.get('msg')}")
        data = body.get("data") or {}
        cols = data.get("fields") or []
        return [dict(zip(cols, row)) for row in (data.get("items") or [])]

    # ---------------- 缓存数据 ----------------

    def _basic_list(self) -> list[dict]:
        """A 股代码表缓存（code/name/industry），TTL 1 小时"""
        cached = self._cache.get("basic")
        if cached is not None:
            return cached
        rows = self._request("stock_basic", {"list_status": "L"},
                             "ts_code,code,name,industry")
        out = [{"ts_code": r["ts_code"], "code": str(r.get("code") or ""),
                "name": r.get("name"), "industry": r.get("industry")} for r in rows]
        self._cache.set("basic", out, 3600)
        return out

    def _latest_trade_date(self) -> str:
        """最近一个已开市交易日（YYYYMMDD），TTL 5 分钟"""
        cached = self._cache.get("trade_date")
        if cached:
            return cached
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        rows = self._request("trade_cal",
                             {"exchange": "SSE", "start_date": start, "end_date": end},
                             "cal_date,is_open")
        dates = sorted(r["cal_date"] for r in rows if str(r.get("is_open")) == "1")
        latest = dates[-1] if dates else end
        self._cache.set("trade_date", latest, 300)
        return latest

    def _daily_snapshot(self) -> dict:
        """最新交易日的全市场 daily_basic 快照（ts_code -> row），TTL 30 秒"""
        cached = self._cache.get("snapshot")
        if cached is not None:
            return cached
        rows = self._request("daily_basic", {"trade_date": self._latest_trade_date()},
                             "ts_code,close,pe,pe_ttm,pb")
        snap = {r["ts_code"]: r for r in rows if r.get("close") is not None}
        self._cache.set("snapshot", snap, 30)
        return snap

    # ---------------- Mock 回退 ----------------

    def _mock_source(self) -> MockDataSource:
        if self._mock is None:
            self._mock = MockDataSource()
        return self._mock

    def _fallback_row(self, code: str) -> dict | None:
        """查询失败/不覆盖时回退 Mock 数据；每个代码仅告警一次"""
        row = self._mock_source().get_quote(code)
        if row is not None and code not in self._warned:
            self._warned.add(code)
            logger.warning("Tushare 未覆盖 %s（或调用失败），本条回退 Mock 数据", code)
        return row

    # ---------------- 基础信息组装 ----------------

    def _basic_info(self, code: str) -> dict:
        for row in self._basic_list():
            if row["code"] == code:
                return row
        return {"code": code, "ts_code": to_ts_code(code) or "",
                "name": code, "industry": None}

    def _row_from_basic(self, basic: dict, quote: dict) -> dict:
        pe = quote.get("pe_ttm") or quote.get("pe")
        return {
            "code": basic["code"], "name": basic.get("name"),
            "market": "CN", "industry": basic.get("industry"),
            "currency": "CNY",
            "pe": round(float(pe), 2) if pe is not None else None,
            "pb": round(float(quote["pb"]), 2) if quote.get("pb") is not None else None,
            "price": round(float(quote["close"]), 2),
            "updated_at": datetime.now().isoformat(),
        }

    # ---------------- DataSourceBase 接口 ----------------

    def list_stocks(self) -> list[dict]:
        """返回配置股票池（TUSHARE_CODES）的行情，共享日线快照（单次 API 调用）"""
        out = []
        for code in self._universe:
            row = self.get_quote(code)
            if row:
                out.append(row)
        return out

    def get_quote(self, code: str) -> dict | None:
        """单码行情：快照命中 -> 单码日线查询 -> 均无则回退 Mock"""
        code = (code or "").strip()
        ts_code = to_ts_code(code)
        if not ts_code:                      # 港股/美股等非 A 股代码直接回退
            return self._fallback_row(code)
        try:
            snap = self._daily_snapshot()
            quote = snap.get(ts_code)
            if quote is None:                # 快照缺失（新股/停牌等）按码查最近 15 个交易日
                start = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
                rows = self._request("daily_basic",
                                     {"ts_code": ts_code, "start_date": start},
                                     "ts_code,close,pe,pe_ttm,pb")
                if rows:
                    quote = rows[-1]
            if quote:
                return self._row_from_basic(self._basic_info(code), quote)
        except TushareAPIError as e:
            logger.warning("Tushare 查询 %s 失败：%s", code, e)
        return self._fallback_row(code)

    def search(self, q: str, market: str | None = None) -> list[dict]:
        """在 A 股代码表中按代码/名称搜索；港股美股命中则回退 Mock 保证可检索"""
        q = (q or "").strip().lower()
        market = (market or "").strip().upper() or None
        if market not in (None, "CN"):        # 港美股筛选：交给 Mock 数据
            rows = self._mock_source().search(q, market)
            return rows

        if not q:
            return self.list_stocks()
        try:
            hits = [b for b in self._basic_list()
                    if q in b["code"].lower() or q in (b.get("name") or "").lower()][:10]
        except TushareAPIError as e:
            logger.warning("Tushare 代码表获取失败，搜索回退 Mock：%s", e)
            return self._mock_source().search(q, market)
        return [row for b in hits if (row := self.get_quote(b["code"]))]

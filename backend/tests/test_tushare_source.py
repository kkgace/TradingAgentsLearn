# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""Tushare 数据源测试：代码映射、行情解析、逐级降级、搜索、管理器选择"""
import pytest

from app.core.config import settings
from app.services.datasources import manager
from app.services.datasources.mock_source import MockDataSource
from app.services.datasources.tushare_source import (TushareAPIError, TushareSource,
                                                     to_ts_code)

# ---- 罐头数据 ----
BASIC_ROWS = [
    {"ts_code": "600519.SH", "code": "600519", "name": "贵州茅台", "industry": "白酒"},
    {"ts_code": "000001.SZ", "code": "000001", "name": "平安银行", "industry": "银行"},
]
SNAPSHOT = {
    "600519.SH": {"ts_code": "600519.SH", "close": 1620.0,
                  "pe": 22.5, "pe_ttm": 22.0, "pb": 8.6},
}
PER_CODE = [
    {"ts_code": "000001.SZ", "close": 11.30, "pe": 4.8, "pe_ttm": 4.7, "pb": 0.55},
    {"ts_code": "000001.SZ", "close": 11.35, "pe": 4.8, "pe_ttm": 4.8, "pb": 0.56},
]


def _canned_source(universe=None) -> TushareSource:
    """_request 打桩：按 api_name 返回罐头数据"""
    src = TushareSource(token="test-token", universe=universe)
    calls: list[str] = []

    def fake_request(api_name, params, fields):
        calls.append(api_name)
        if api_name == "stock_basic":
            return BASIC_ROWS
        if api_name == "trade_cal":
            return [{"cal_date": "20260924", "is_open": "1"}]
        if api_name == "daily_basic":
            if params.get("ts_code"):            # 单码近 15 日查询
                return PER_CODE if params["ts_code"] == "000001.SZ" else []
            return [dict(v) for v in SNAPSHOT.values()]   # 全市场快照
        raise AssertionError(f"未预期的接口: {api_name}")

    src._request = fake_request
    src._calls = calls
    return src


# ---------- 代码 -> ts_code 映射 ----------

def test_to_ts_code_mapping():
    assert to_ts_code("600519") == "600519.SH"
    assert to_ts_code("689009") == "689009.SH"
    assert to_ts_code("000001") == "000001.SZ"
    assert to_ts_code("300750") == "300750.SZ"
    assert to_ts_code("002594") == "002594.SZ"
    assert to_ts_code("830799") == "830799.BJ"
    assert to_ts_code("00700") is None          # 港股
    assert to_ts_code("AAPL") is None           # 美股
    assert to_ts_code("") is None


# ---------- 行情解析 ----------

def test_get_quote_snapshot_hit():
    q = _canned_source().get_quote("600519")
    assert q["code"] == "600519" and q["name"] == "贵州茅台"
    assert q["market"] == "CN" and q["currency"] == "CNY"
    assert q["price"] == 1620.0
    assert q["pe"] == 22.0                      # pe_ttm 优先
    assert q["pb"] == 8.6
    assert q["updated_at"]


def test_get_quote_per_code_latest_row():
    q = _canned_source().get_quote("000001")    # 不在快照 -> 单码查询取最后一行
    assert q["price"] == 11.35 and q["pe"] == 4.8 and q["pb"] == 0.56


# ---------- 逐级降级 ----------

def test_get_quote_api_error_falls_back_to_mock():
    src = TushareSource(token="t")

    def boom(api_name, params, fields):
        raise TushareAPIError("积分不足")

    src._request = boom
    q = src.get_quote("600519")
    assert q is not None and q["name"] == "贵州茅台"
    assert abs(q["price"] - 1620.0) <= 1620.0 * 0.05      # Mock 漂移价
    assert "600519" in src._warned                        # 只告警一次
    q2 = src.get_quote("600519")
    assert q2["code"] == q["code"] and q2["name"] == q["name"]   # 回退稳定
    assert abs(q2["price"] - 1620.0) <= 1620.0 * 0.05


def test_get_quote_non_cn_uses_mock_without_api_call():
    src = _canned_source()
    q = src.get_quote("00700")
    assert q["market"] == "HK" and q["name"] == "腾讯控股"
    assert src._calls == []                               # 未发起任何 Tushare 请求


def test_get_quote_unknown_cn_code_falls_back():
    src = _canned_source()                                # 999999 不在罐头数据
    q = src.get_quote("999999")
    assert q is None                                       # Mock 也没有 -> None


# ---------- 搜索与股票池 ----------

def test_search_by_name():
    src = _canned_source()
    rows = src.search("茅台")
    assert [r["code"] for r in rows] == ["600519"]
    assert rows[0]["price"] == 1620.0                      # 搜索结果带行情


def test_search_by_code_and_limit():
    rows = _canned_source().search("000")
    assert {r["code"] for r in rows} == {"000001"}


def test_search_non_cn_market_delegates_to_mock():
    rows = _canned_source().search("", market="HK")
    assert all(r["market"] == "HK" for r in rows)
    assert len(rows) == 5


def test_list_stocks_universe():
    src = _canned_source(universe=["600519", "000001"])
    rows = src.list_stocks()
    assert {r["code"] for r in rows} == {"600519", "000001"}


# ---------- 管理器选择 ----------

def test_manager_no_token_uses_mock(monkeypatch):
    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "")
    monkeypatch.setattr(manager, "_source", None)
    assert isinstance(manager.get_source(), MockDataSource)


def test_manager_token_uses_tushare_and_caches(monkeypatch):
    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "test-token")
    monkeypatch.setattr(manager, "_source", None)
    src = manager.get_source()
    assert isinstance(src, TushareSource)
    assert manager.get_source() is src                # 单例缓存

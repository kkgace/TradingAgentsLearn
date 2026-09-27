# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""Mock 数据源测试：价格漂移的确定性、有界性，以及查询接口形状"""
from app.services.datasources.mock_source import _MOCK_STOCKS, MockDataSource, _drift_price


def test_drift_deterministic_within_bucket():
    # 同一 30 秒档内任意时刻取价一致（可复现）
    assert _drift_price(100.0, "600519", now=900) == _drift_price(100.0, "600519", now=929)


def test_drift_is_pure_function():
    a = _drift_price(1620.0, "AAPL", now=12345)
    b = _drift_price(1620.0, "AAPL", now=12345)
    assert a == b


def test_drift_varies_across_buckets():
    prices = {_drift_price(100.0, "600519", now=t) for t in range(0, 3000, 30)}
    assert len(prices) > 5            # 静态价则只有 1 个值


def test_drift_bounded_within_5_percent():
    for now in range(0, 30000, 7):
        p = _drift_price(1620.0, "600519", now=now)
        assert 1620.0 * 0.95 - 0.01 <= p <= 1620.0 * 1.05 + 0.01


def test_quote_shape_and_anchor():
    src = MockDataSource()
    q = src.get_quote("600519")
    anchor = next(s for s in _MOCK_STOCKS if s["code"] == "600519")["price"]
    assert q["name"] == "贵州茅台"
    assert abs(q["price"] - anchor) <= anchor * 0.045
    assert q["updated_at"]


def test_quote_missing_code():
    assert MockDataSource().get_quote("NOPE999") is None


def test_list_stocks_count():
    assert len(MockDataSource().list_stocks()) == len(_MOCK_STOCKS) == 20


def test_search_by_name_and_market_filter():
    src = MockDataSource()
    rows = src.search("茅台")
    assert [r["code"] for r in rows] == ["600519"]
    us = src.search("", market="US")
    assert us and all(r["market"] == "US" for r in us)

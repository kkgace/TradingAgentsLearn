# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""模拟盘引擎单元测试：市场识别、佣金规则、买卖撮合、已实现盈亏"""
import pytest

from app.models import PaperPosition, Stock
from app.services import paper_engine
from app.services.paper_engine import get_account


def _add_stock(db, code="600519", price=10.0, market="CN", currency="CNY"):
    st = Stock(code=code, name="测试股", market=market, currency=currency, price=price)
    db.add(st)
    db.commit()
    return st


# ---------- 市场识别 ----------

def test_detect_market():
    assert paper_engine.detect_market("600519") == "CN"
    assert paper_engine.detect_market("000001") == "CN"
    assert paper_engine.detect_market("00700") == "HK"
    assert paper_engine.detect_market("09988") == "HK"
    assert paper_engine.detect_market("AAPL") == "US"
    assert paper_engine.detect_market("aapl") == "US"     # 大小写归一


# ---------- 佣金规则 ----------

def test_commission_cn_min_five():
    assert paper_engine._commission("CN", "buy", 1000.0) == 5.0      # 万3不足 5 元按 5
    assert paper_engine._commission("CN", "buy", 100000.0) == 30.0   # 万3 = 30


def test_commission_hk_stamp_duty_only_on_sell():
    assert paper_engine._commission("HK", "buy", 10000.0) == 3.0
    assert paper_engine._commission("HK", "sell", 10000.0) == 16.0   # 3 + 印花税 13


def test_commission_us_free():
    assert paper_engine._commission("US", "buy", 999999.0) == 0.0


# ---------- 下单：买入 ----------

def test_place_order_buy_updates_cash_and_position(db, user):
    _add_stock(db, price=10.0)
    order = paper_engine.place_order(db, user.id, "600519", "buy", 200, price=10.0)
    assert order.status == "filled"
    assert order.commission == 5.0
    acc = get_account(db, user.id)
    assert acc.cash_cny == round(1000000.0 - (2000.0 + 5.0), 2)
    pos = db.query(PaperPosition).first()
    assert pos.qty == 200
    assert pos.avg_cost == round((2000.0 + 5.0) / 200, 2)   # 均价含买入佣金


def test_place_order_buy_rejects_insufficient_cash(db, user):
    _add_stock(db, price=10.0)
    order = paper_engine.place_order(db, user.id, "600519", "buy", 99999999, price=10.0)
    assert order.status == "rejected"
    assert "现金不足" in order.reason
    assert db.query(PaperPosition).count() == 0


def test_place_order_price_defaults_to_stock_table(db, user):
    _add_stock(db, price=12.34)
    order = paper_engine.place_order(db, user.id, "600519", "buy", 100)
    assert order.status == "filled"
    assert order.price == 12.34


# ---------- 下单：卖出与已实现盈亏 ----------

def test_place_order_sell_realized_pnl(db, user):
    _add_stock(db, price=10.0)
    paper_engine.place_order(db, user.id, "600519", "buy", 100, price=10.0)
    order = paper_engine.place_order(db, user.id, "600519", "sell", 100, price=12.0)
    assert order.status == "filled"
    acc = get_account(db, user.id)
    # 买入均价 10.05（含佣）；卖出 12 元，佣金最低 5 元 -> pnl=(12-10.05)*100-5=190
    assert acc.realized_pnl_cny == round((12.0 - 10.05) * 100 - 5.0, 2)
    assert db.query(PaperPosition).count() == 0      # 清仓删持仓


def test_place_order_sell_rejects_without_position(db, user):
    _add_stock(db, price=10.0)
    order = paper_engine.place_order(db, user.id, "600519", "sell", 100, price=10.0)
    assert order.status == "rejected"
    assert "持仓不足" in order.reason


# ---------- 参数校验 ----------

def test_place_order_validates_input(db, user):
    with pytest.raises(ValueError):
        paper_engine.place_order(db, user.id, "", "buy", 100)
    with pytest.raises(ValueError):
        paper_engine.place_order(db, user.id, "600519", "hold", 100)
    with pytest.raises(ValueError):
        paper_engine.place_order(db, user.id, "600519", "buy", 0)
    with pytest.raises(ValueError):
        paper_engine.place_order(db, user.id, "600519", "buy", None)

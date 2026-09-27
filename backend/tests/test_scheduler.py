# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""调度器测试：命中判定、按手数估算数量、触发 -> 自动下单 -> 计划闭环"""
import json

from app.models import PaperOrder, Plan, Stock, Trigger
from app.services import paper_engine
from app.worker.scheduler import _calc_qty, _hit, _poll_triggers


def _add_stock(db, code="300001", price=10.0):
    st = Stock(code=code, name="测试股", market="CN", currency="CNY", price=price)
    db.add(st)
    db.commit()
    return st


def _add_plan_trigger(db, user_id, code, direction, target, entry_price=10.0,
                      plan_status="active", trig_type="price_above"):
    plan = Plan(user_id=user_id, code=code, direction=direction,
                entry_price=entry_price, status=plan_status)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    trig = Trigger(user_id=user_id, plan_id=plan.id, type=trig_type,
                   params=json.dumps({"price": target}), status="on")
    db.add(trig)
    db.commit()
    db.refresh(trig)
    return plan, trig


# ---------- 纯函数 ----------

def test_hit_price_above_and_below():
    assert _hit("price_above", 10.0, 10.01)
    assert not _hit("price_above", 10.0, 9.99)
    assert _hit("price_below", 10.0, 9.99)
    assert not _hit("price_below", 10.0, 10.01)
    assert not _hit("ma_cross", 10.0, 9.99)     # 未支持类型一律不命中


def test_calc_qty_respects_lot_size_and_fx():
    assert _calc_qty("CN", 10.0, 20000.0) == 2000          # 2 手 * 100
    assert _calc_qty("CN", 33.45, 20000.0) == 500          # 5 手 * 100
    assert _calc_qty("US", 100.0, 7200.0) == 10           # CNY 预算折 USD
    assert _calc_qty("CN", 0.0, 20000.0) == 0             # 非法价格


# ---------- 触发闭环 ----------

def test_poll_fires_buy_trigger_and_completes_plan(db, user):
    # 300001 不在 Mock 池中，行情刷新不会覆盖手工价格，结果确定
    _add_stock(db, price=10.0)
    plan, trig = _add_plan_trigger(db, user.id, "300001", "buy", target=9.0)

    _poll_triggers()
    db.expire_all()

    assert db.query(Trigger).first().status == "fired"
    assert db.query(Plan).first().status == "done"
    orders = db.query(PaperOrder).all()
    assert len(orders) == 1
    assert orders[0].side == "buy" and orders[0].status == "filled"
    assert orders[0].qty == _calc_qty("CN", 10.0, 20000.0)
    assert orders[0].plan_id == plan.id


def test_poll_sell_trigger_sells_whole_position(db, user):
    _add_stock(db, price=10.0)
    paper_engine.place_order(db, user.id, "300001", "buy", 100, price=10.0)   # 建仓
    _add_plan_trigger(db, user.id, "300001", "sell", target=9.0)

    _poll_triggers()
    db.expire_all()

    assert db.query(Trigger).first().status == "fired"
    sell_orders = [o for o in db.query(PaperOrder).all() if o.side == "sell"]
    assert len(sell_orders) == 1
    assert sell_orders[0].qty == 100          # 卖出全部持仓
    assert sell_orders[0].status == "filled"


def test_poll_sell_without_position_marks_skipped(db, user):
    _add_stock(db, price=10.0)
    _add_plan_trigger(db, user.id, "300001", "sell", target=9.0)

    _poll_triggers()
    db.expire_all()

    assert db.query(Trigger).first().status == "fired"      # 触发器仍消耗
    assert db.query(PaperOrder).count() == 0                # 但不产生订单


def test_poll_ignores_cancelled_plan(db, user):
    _add_stock(db, price=10.0)
    _add_plan_trigger(db, user.id, "300001", "buy", target=9.0, plan_status="cancelled")

    _poll_triggers()
    db.expire_all()

    assert db.query(Trigger).first().status == "on"         # 不动
    assert db.query(PaperOrder).count() == 0


def test_poll_noop_without_triggers(db, user):
    _add_stock(db, price=10.0)
    _poll_triggers()                                        # 空表不抛异常
    assert db.query(Trigger).count() == 0

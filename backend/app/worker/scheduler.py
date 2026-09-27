# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""后台调度器：触发器价格轮询。

- 每 TRIGGER_POLL_SECONDS 秒扫描 status=on 的触发器（type: price_above / price_below）
- 判定前先从数据源刷新相关股票的最新价（mock 源为时间确定性漂移价）
- 以 Stock.price 判定命中：命中后置 fired/fired_at、计划置 done，并执行一笔模拟单
  （buy 按预算估算数量；sell 卖出当前全部持仓，无持仓则记录 skipped）
- 命中后通过 sse_bus 发布 topic="triggers" 事件
- 注意：job 运行在后台线程，必须自建 SessionLocal 并在 finally 中关闭；所有异常吞噬，避免拖垮调度器
"""
import json
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Plan, PaperPosition, Stock, Trigger
from app.services import paper_engine
from app.services.datasources.manager import get_source
from app.services.sse_bus import bus

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

# 各市场最小买入手数
LOT_SIZE = {"CN": 100, "HK": 100, "US": 1}

# 触发买入的默认预算（CNY）；后续可接用户设置
BUY_BUDGET_CNY = 20000.0


def _hit(trigger_type: str, target: float, current: float) -> bool:
    """判定是否命中：price_above 现价>=目标；price_below 现价<=目标"""
    if trigger_type == "price_above":
        return current >= target
    if trigger_type == "price_below":
        return current <= target
    return False


def _calc_qty(market: str, price: float, budget_cny: float) -> int:
    """按预算（折算 CNY）与最小手数估算买入数量"""
    lot = LOT_SIZE.get(market, 1)
    fx = {"CN": 1.0, "HK": 1.0 / 0.92, "US": 1.0 / 7.2}.get(market, 1.0)  # CNY -> 本币
    budget_native = budget_cny * fx
    if price <= 0:
        return 0
    qty = int(budget_native // (price * lot)) * lot
    return max(qty, 0)


def _refresh_prices(db, codes: set[str]) -> None:
    """判定前把数据源最新价刷进 Stock 表（mock 源为漂移价）；单只失败跳过"""
    for code in codes:
        try:
            row = get_source().get_quote(code)
            if not row or not row.get("price"):
                continue
            st = db.query(Stock).filter(Stock.code == code).first()
            if st:
                st.price = float(row["price"])
                st.updated_at = datetime.now()
        except Exception:
            continue
    try:
        db.commit()
    except Exception:
        db.rollback()


def _sell_qty(db, user_id: int, code: str) -> int:
    """卖出方向的可卖数量 = 当前全部持仓"""
    pos = (db.query(PaperPosition)
           .filter(PaperPosition.user_id == user_id, PaperPosition.code == code).first())
    return int(pos.qty) if pos else 0


def _poll_triggers():
    """扫描一次全部开启中的触发器；单条异常不影响其他，整体异常吞噬"""
    db = SessionLocal()
    try:
        triggers = db.query(Trigger).filter(Trigger.status == "on").all()
        if not triggers:
            return
        plan_ids = {t.plan_id for t in triggers}
        plans = {p.id: p for p in db.query(Plan).filter(Plan.id.in_(plan_ids)).all()}
        # 判定前刷新涉及股票的行情（mock 漂移价随时间变化，保证触发器可真实演示）
        live_codes = {p.code for p in plans.values() if p.status in ("draft", "active")}
        if live_codes:
            _refresh_prices(db, live_codes)

        for trig in triggers:
            try:
                # 解析参数中的目标价
                try:
                    params = json.loads(trig.params) if trig.params else {}
                except (ValueError, TypeError):
                    continue
                target = params.get("price")
                if target is None:
                    continue
                target = float(target)

                plan = plans.get(trig.plan_id)
                if not plan or plan.status not in ("draft", "active"):
                    continue
                stock = db.query(Stock).filter(Stock.code == plan.code).first()
                if not stock or not stock.price:
                    continue
                current = round(float(stock.price), 2)

                if not _hit(trig.type, target, current):
                    continue

                # 命中：标记 fired、计划完成，并执行一笔模拟单（买卖均按计划方向）
                trig.status = "fired"
                trig.fired_at = datetime.now()
                plan.status = "done"
                side = "buy" if plan.direction in ("buy", "hold") else "sell"
                price = float(plan.entry_price) if plan.entry_price else current
                market = paper_engine.detect_market(plan.code)
                if side == "buy":
                    qty = _calc_qty(market, price, BUY_BUDGET_CNY)
                else:
                    qty = _sell_qty(db, trig.user_id, plan.code)
                order_info = None
                if qty > 0:
                    try:
                        order = paper_engine.place_order(
                            db, trig.user_id, plan.code, side, qty,
                            price=round(price, 2), plan_id=plan.id)
                        order_info = {
                            "order_id": order.id, "status": order.status,
                            "qty": order.qty, "price": order.price,
                            "reason": order.reason,
                        }
                    except ValueError as e:
                        order_info = {"status": "rejected", "reason": str(e)}
                else:
                    order_info = {
                        "status": "skipped",
                        "reason": "买入预算不足一手" if side == "buy" else "无可卖持仓",
                    }
                db.commit()
                logger.info("触发器命中：trigger=%s plan=%s code=%s side=%s qty=%s order=%s",
                            trig.id, plan.id, plan.code, side, qty, order_info)

                bus.publish("triggers", {
                    "type": "trigger_fired",
                    "trigger_id": trig.id,
                    "plan_id": plan.id,
                    "code": plan.code,
                    "trigger_type": trig.type,
                    "target_price": target,
                    "current_price": current,
                    "order": order_info,
                    "note": "本系统仅用于学习研究，不构成投资建议",
                })
            except Exception:
                db.rollback()
                continue
    except Exception:
        pass
    finally:
        db.close()


def start_scheduler():
    """启动后台调度器（幂等；ENABLE_SCHEDULER=False 时不启动）"""
    global _scheduler
    if not settings.ENABLE_SCHEDULER:
        return None
    if _scheduler is not None:
        return _scheduler
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        _poll_triggers,
        trigger="interval",
        seconds=max(5, int(settings.TRIGGER_POLL_SECONDS)),
        id="trigger_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    return _scheduler

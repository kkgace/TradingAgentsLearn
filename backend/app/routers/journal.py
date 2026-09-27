# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""复盘路由：journal_entries CRUD + GET /journal/stats 近 30 天模拟盘成交统计。

统计口径说明：
- 胜率：近 30 天内卖出订单中，按「移动平均成本」重放估算的单笔 PnL > 0 的比例；
- 平均单笔 PnL：上述卖出订单 PnL（含佣金，并统一折算为 CNY 口径相对值，直接用订单价）的算术平均；
- 按计划执行率：近 30 天全部成交订单中带 plan_id 的占比。
由于 PaperOrder 表无 pnl 字段，此处按时间顺序重放全部订单以还原逐笔卖出成本。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, ok, fail
from app.models import JournalEntry, PaperOrder, Plan, User

router = APIRouter(prefix="/journal", tags=["journal"])


class JournalCreate(BaseModel):
    title: str
    content: Optional[str] = None
    plan_id: Optional[int] = None
    pnl: Optional[float] = None
    adherence_score: Optional[float] = None


class JournalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    plan_id: Optional[int] = None
    pnl: Optional[float] = None
    adherence_score: Optional[float] = None


def _serialize(e: JournalEntry) -> dict:
    """序列化复盘条目为前端友好字典"""
    return {
        "id": e.id,
        "plan_id": e.plan_id,
        "title": e.title,
        "content": e.content,
        "pnl": e.pnl,
        "adherence_score": e.adherence_score,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("")
def list_entries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户复盘日记列表，按创建时间倒序"""
    try:
        rows = (
            db.query(JournalEntry)
            .filter(JournalEntry.user_id == user.id)
            .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
            .all()
        )
        return ok([_serialize(r) for r in rows])
    except Exception as e:
        return fail(f"查询复盘列表失败: {e}")


@router.post("")
def create_entry(
    body: JournalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """新建复盘日记；如带 plan_id 则校验计划归属当前用户"""
    try:
        title = (body.title or "").strip()
        if not title:
            return fail("标题不能为空")
        if body.plan_id is not None:
            plan = (
                db.query(Plan)
                .filter(Plan.id == body.plan_id, Plan.user_id == user.id)
                .first()
            )
            if not plan:
                return fail("关联计划不存在或不属于当前用户")
        entry = JournalEntry(
            user_id=user.id,
            plan_id=body.plan_id,
            title=title,
            content=body.content or "",
            pnl=body.pnl,
            adherence_score=body.adherence_score,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return ok(_serialize(entry), msg="已保存复盘")
    except Exception as e:
        db.rollback()
        return fail(f"创建复盘失败: {e}")


@router.put("/{entry_id}")
def update_entry(
    entry_id: int,
    body: JournalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新复盘日记（仅限当前用户所有，仅更新传入的字段）"""
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
            .first()
        )
        if not entry:
            return fail("复盘记录不存在")
        if body.title is not None:
            title = body.title.strip()
            if not title:
                return fail("标题不能为空")
            entry.title = title
        if body.content is not None:
            entry.content = body.content
        if body.plan_id is not None:
            plan = (
                db.query(Plan)
                .filter(Plan.id == body.plan_id, Plan.user_id == user.id)
                .first()
            )
            if not plan:
                return fail("关联计划不存在或不属于当前用户")
            entry.plan_id = body.plan_id
        if body.pnl is not None:
            entry.pnl = body.pnl
        if body.adherence_score is not None:
            entry.adherence_score = body.adherence_score
        db.commit()
        db.refresh(entry)
        return ok(_serialize(entry), msg="已更新")
    except Exception as e:
        db.rollback()
        return fail(f"更新复盘失败: {e}")


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除复盘日记（仅限当前用户所有）"""
    try:
        entry = (
            db.query(JournalEntry)
            .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
            .first()
        )
        if not entry:
            return fail("复盘记录不存在")
        db.delete(entry)
        db.commit()
        return ok({"id": entry_id}, msg="已删除")
    except Exception as e:
        db.rollback()
        return fail(f"删除复盘失败: {e}")


# 折人民币参考汇率（与模拟盘 engine 口径一致）
FX_TO_CNY = {"CNY": 1.0, "HKD": 0.92, "USD": 7.2}


def _replay_sell_pnls(orders: list[PaperOrder]) -> list[tuple[PaperOrder, float]]:
    """按时间重放全部成交订单，用移动平均成本估算每笔卖出的已实现 PnL（折 CNY，含佣金）。

    返回 [(order, pnl_cny), ...]，仅包含卖出单。
    """
    positions: dict[str, dict[str, float]] = {}  # code -> {qty, avg_cost, currency}
    results: list[tuple[PaperOrder, float]] = []
    for o in orders:
        if o.status != "filled":
            continue
        pos = positions.setdefault(o.code, {"qty": 0.0, "avg_cost": 0.0, "currency": o.currency or "CNY"})
        comm = float(o.commission or 0.0)
        if o.side == "buy":
            new_qty = pos["qty"] + o.qty
            if new_qty > 0:
                pos["avg_cost"] = (pos["avg_cost"] * pos["qty"] + o.price * o.qty + comm) / new_qty
            pos["qty"] = new_qty
        else:
            pnl_gross = (o.price - pos["avg_cost"]) * o.qty
            pnl_local = pnl_gross - comm  # 卖出佣金从收益中扣除
            results.append((o, pnl_local * FX_TO_CNY.get(o.currency or pos["currency"], 1.0)))
            pos["qty"] = max(pos["qty"] - o.qty, 0.0)
            if pos["qty"] == 0:
                pos["avg_cost"] = 0.0
    return results


@router.get("/stats")
def journal_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """近 30 天模拟盘成交统计：胜率、平均单笔 PnL、按计划执行率"""
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        # 重放需全部历史（成本依赖更早的买入）；统计窗口只筛近 30 天
        all_orders = (
            db.query(PaperOrder)
            .filter(PaperOrder.user_id == user.id, PaperOrder.status == "filled")
            .order_by(PaperOrder.created_at.asc(), PaperOrder.id.asc())
            .all()
        )
        sell_pnls_all = _replay_sell_pnls(all_orders)
        sell_pnls = [
            pnl for o, pnl in sell_pnls_all
            if o.created_at is not None and o.created_at >= cutoff
        ]
        sell_total = len(sell_pnls)
        wins = sum(1 for p in sell_pnls if p > 0)
        win_rate = round(wins / sell_total, 4) if sell_total else None
        avg_pnl = round(sum(sell_pnls) / sell_total, 2) if sell_total else 0.0

        recent_orders = [
            o for o in all_orders
            if o.created_at is not None and o.created_at >= cutoff
        ]
        order_total = len(recent_orders)
        with_plan = sum(1 for o in recent_orders if o.plan_id is not None)
        adherence = round(with_plan / order_total, 4) if order_total else None

        return ok({
            "days": 30,
            "sell_order_count": sell_total,
            "win_count": wins,
            "win_rate": win_rate,                # 卖出胜率（0~1），无卖出单为 null
            "avg_pnl_per_sell": avg_pnl,          # 平均单笔卖出 PnL（折 CNY）
            "total_pnl": round(sum(sell_pnls), 2),
            "order_count": order_total,
            "orders_with_plan": with_plan,
            "plan_adherence": adherence,          # 按计划执行率（0~1），无订单为 null
            "disclaimer": "本系统仅用于学习研究，不构成投资建议",
        })
    except Exception as e:
        return fail(f"统计复盘数据失败: {e}")

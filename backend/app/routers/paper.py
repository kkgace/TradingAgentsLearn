# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""模拟盘路由：账户/持仓/下单/订单历史"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ok, fail, get_current_user
from app.models import PaperOrder, PaperPosition
from app.services import paper_engine

router = APIRouter(prefix="/paper", tags=["paper"])

DISCLAIMER = "本系统仅用于学习研究，不构成投资建议"


class OrderIn(BaseModel):
    code: str
    side: str                       # buy|sell
    qty: int
    price: Optional[float] = None   # 缺省取 Stock.price
    plan_id: Optional[int] = None


def _account_dict(acc) -> dict:
    return {
        "user_id": acc.user_id,
        "cash_cny": round(acc.cash_cny or 0.0, 2),
        "cash_hkd": round(acc.cash_hkd or 0.0, 2),
        "cash_usd": round(acc.cash_usd or 0.0, 2),
        "realized_pnl_cny": round(acc.realized_pnl_cny or 0.0, 2),
    }


def _order_dict(o: PaperOrder) -> dict:
    return {
        "id": o.id,
        "plan_id": o.plan_id,
        "code": o.code,
        "market": o.market,
        "side": o.side,
        "qty": o.qty,
        "price": round(o.price, 2),
        "currency": o.currency,
        "commission": round(o.commission or 0.0, 2),
        "status": o.status,
        "reason": o.reason,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _position_dict(p: PaperPosition) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "market": p.market,
        "qty": p.qty,
        "avg_cost": round(p.avg_cost or 0.0, 2),
        "currency": p.currency,
    }


@router.get("/account")
def get_account(db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        acc = paper_engine.get_account(db, user.id)
        return ok(_account_dict(acc), msg=DISCLAIMER)
    except Exception as e:
        return fail(f"查询账户失败：{e}")


@router.get("/positions")
def list_positions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        items = (db.query(PaperPosition)
                 .filter(PaperPosition.user_id == user.id, PaperPosition.qty > 0)
                 .order_by(PaperPosition.id.desc()).all())
        return ok([_position_dict(p) for p in items])
    except Exception as e:
        return fail(f"查询持仓失败：{e}")


@router.post("/order")
def place_order(body: OrderIn, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    try:
        order = paper_engine.place_order(
            db, user.id, body.code, body.side, body.qty,
            price=body.price, plan_id=body.plan_id)
    except ValueError as e:
        return fail(str(e))
    except Exception as e:
        db.rollback()
        return fail(f"下单失败：{e}")
    if order.status == "rejected":
        return fail(order.reason or "订单被拒绝")
    return ok(_order_dict(order), msg=f"已成交。{DISCLAIMER}")


@router.get("/orders")
def list_orders(limit: int = 100, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    try:
        limit = max(1, min(int(limit or 100), 500))
        items = (db.query(PaperOrder)
                 .filter(PaperOrder.user_id == user.id)
                 .order_by(PaperOrder.id.desc()).limit(limit).all())
        return ok([_order_dict(o) for o in items])
    except Exception as e:
        return fail(f"查询订单失败：{e}")

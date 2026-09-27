# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""触发器路由：GET/POST/PUT/DELETE /triggers
- type: price_above / price_below；params JSON {"price": x}
- 创建时校验 plan 归属当前用户且 plan.status 为 draft/active
- DELETE 为逻辑关闭（status=off），不物理删除
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, ok, fail
from app.models import Plan, Trigger, User

router = APIRouter(prefix="/triggers", tags=["triggers"])

VALID_TYPES = ("price_above", "price_below")


class TriggerCreate(BaseModel):
    plan_id: int
    type: str                      # price_above / price_below
    params: Optional[dict] = None  # {"price": 12.34}
    price: Optional[float] = None  # 便捷字段，与 params.price 二选一


class TriggerUpdate(BaseModel):
    type: Optional[str] = None
    params: Optional[dict] = None
    price: Optional[float] = None
    status: Optional[str] = None   # on/off


def _serialize(t: Trigger, plan: Plan | None = None) -> dict:
    """序列化触发器，附带关联计划摘要"""
    try:
        params = json.loads(t.params) if t.params else {}
    except (ValueError, TypeError):
        params = {}
    return {
        "id": t.id,
        "plan_id": t.plan_id,
        "type": t.type,
        "params": params,
        "price": params.get("price"),
        "status": t.status,
        "fired_at": t.fired_at.isoformat() if t.fired_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "plan_code": plan.code if plan else None,
        "plan_status": plan.status if plan else None,
        "plan_direction": plan.direction if plan else None,
    }


def _parse_price(body_price: Optional[float], params: Optional[dict]) -> tuple[float | None, str | None]:
    """解析触发价格：优先 params.price，其次顶层 price；返回 (price, error)"""
    price = None
    if params and params.get("price") is not None:
        try:
            price = float(params["price"])
        except (TypeError, ValueError):
            return None, "params.price 必须是数字"
    elif body_price is not None:
        price = float(body_price)
    if price is None:
        return None, "缺少触发价格（params.price 或 price）"
    if price <= 0:
        return None, "触发价格必须大于 0"
    return round(price, 2), None


@router.get("")
def list_triggers(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户触发器列表（可选按 status 过滤），按创建时间倒序"""
    try:
        q = db.query(Trigger).filter(Trigger.user_id == user.id)
        if status:
            q = q.filter(Trigger.status == status)
        triggers = q.order_by(Trigger.created_at.desc(), Trigger.id.desc()).all()
        plan_ids = {t.plan_id for t in triggers}
        plans = {p.id: p for p in db.query(Plan).filter(Plan.id.in_(plan_ids)).all()} if plan_ids else {}
        return ok([_serialize(t, plans.get(t.plan_id)) for t in triggers])
    except Exception as e:
        return fail(f"查询触发器失败: {e}")


@router.post("")
def create_trigger(
    body: TriggerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """新建触发器：校验 type、价格与关联计划归属/状态"""
    try:
        # 校验类型
        ttype = (body.type or "").strip()
        if ttype not in VALID_TYPES:
            return fail(f"不支持的触发类型: {ttype}（仅支持 price_above/price_below）")
        # 校验价格
        price, err = _parse_price(body.price, body.params)
        if err:
            return fail(err)
        # 校验计划归属与状态
        plan = (
            db.query(Plan)
            .filter(Plan.id == body.plan_id, Plan.user_id == user.id)
            .first()
        )
        if not plan:
            return fail("计划不存在或不属于当前用户")
        if plan.status not in ("draft", "active"):
            return fail(f"仅可为 draft/active 状态的计划创建触发器（当前: {plan.status}）")
        trig = Trigger(
            user_id=user.id,
            plan_id=plan.id,
            type=ttype,
            params=json.dumps({"price": price}, ensure_ascii=False),
            status="on",
        )
        db.add(trig)
        db.commit()
        db.refresh(trig)
        return ok(_serialize(trig, plan), msg="触发器已创建")
    except Exception as e:
        db.rollback()
        return fail(f"创建触发器失败: {e}")


@router.put("/{trigger_id}")
def update_trigger(
    trigger_id: int,
    body: TriggerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新触发器（类型/价格/开关）；已 fired 的触发器不可再修改"""
    try:
        trig = (
            db.query(Trigger)
            .filter(Trigger.id == trigger_id, Trigger.user_id == user.id)
            .first()
        )
        if not trig:
            return fail("触发器不存在")
        if trig.status == "fired":
            return fail("已触发的触发器不可修改")
        if body.type is not None:
            ttype = body.type.strip()
            if ttype not in VALID_TYPES:
                return fail(f"不支持的触发类型: {ttype}")
            trig.type = ttype
        if body.params is not None or body.price is not None:
            price, err = _parse_price(body.price, body.params)
            if err:
                return fail(err)
            trig.params = json.dumps({"price": price}, ensure_ascii=False)
        if body.status is not None:
            if body.status not in ("on", "off"):
                return fail("status 仅支持 on/off")
            trig.status = body.status
        db.commit()
        db.refresh(trig)
        plan = db.query(Plan).filter(Plan.id == trig.plan_id).first()
        return ok(_serialize(trig, plan), msg="触发器已更新")
    except Exception as e:
        db.rollback()
        return fail(f"更新触发器失败: {e}")


@router.delete("/{trigger_id}")
def delete_trigger(
    trigger_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除触发器（逻辑关闭：status=off，保留记录便于审计）"""
    try:
        trig = (
            db.query(Trigger)
            .filter(Trigger.id == trigger_id, Trigger.user_id == user.id)
            .first()
        )
        if not trig:
            return fail("触发器不存在")
        trig.status = "off"
        db.commit()
        return ok({"id": trigger_id, "status": "off"}, msg="触发器已关闭")
    except Exception as e:
        db.rollback()
        return fail(f"关闭触发器失败: {e}")

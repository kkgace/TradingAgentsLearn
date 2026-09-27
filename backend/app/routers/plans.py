# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""交易计划路由：CRUD + 从分析结论一键生成计划"""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ok, fail, get_current_user
from app.models import Plan, Analysis

router = APIRouter(prefix="/plans", tags=["plans"])


class PlanIn(BaseModel):
    code: str
    direction: str = "buy"                     # buy|hold|reduce|sell
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    risk_pct: float = 0.01
    note: Optional[str] = None
    status: str = "draft"                      # draft|active|done|cancelled
    analysis_id: Optional[int] = None


class PlanUpdate(BaseModel):
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    risk_pct: Optional[float] = None
    note: Optional[str] = None
    status: Optional[str] = None


def _to_dict(p: Plan) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "analysis_id": p.analysis_id,
        "code": p.code,
        "direction": p.direction,
        "entry_price": round(p.entry_price, 2) if p.entry_price is not None else None,
        "stop_price": round(p.stop_price, 2) if p.stop_price is not None else None,
        "target_price": round(p.target_price, 2) if p.target_price is not None else None,
        "risk_pct": p.risk_pct,
        "note": p.note,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _get_owned(db: Session, plan_id: int, user_id: int) -> Optional[Plan]:
    return db.query(Plan).filter(Plan.id == plan_id, Plan.user_id == user_id).first()


@router.get("")
def list_plans(status: Optional[str] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user)):
    try:
        q = db.query(Plan).filter(Plan.user_id == user.id)
        if status:
            q = q.filter(Plan.status == status)
        items = q.order_by(Plan.id.desc()).all()
        return ok([_to_dict(p) for p in items])
    except Exception as e:
        return fail(f"查询计划失败：{e}")


@router.post("")
def create_plan(body: PlanIn, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    try:
        if body.direction not in ("buy", "hold", "reduce", "sell"):
            return fail("direction 必须为 buy|hold|reduce|sell")
        if body.status not in ("draft", "active", "done", "cancelled"):
            return fail("status 必须为 draft|active|done|cancelled")
        p = Plan(
            user_id=user.id,
            analysis_id=body.analysis_id,
            code=body.code.strip(),
            direction=body.direction,
            entry_price=body.entry_price,
            stop_price=body.stop_price,
            target_price=body.target_price,
            risk_pct=body.risk_pct,
            note=body.note,
            status=body.status,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return ok(_to_dict(p), msg="计划已创建。本系统仅用于学习研究，不构成投资建议")
    except Exception as e:
        db.rollback()
        return fail(f"创建计划失败：{e}")


@router.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _get_owned(db, plan_id, user.id)
    if not p:
        return fail("计划不存在", code=404)
    return ok(_to_dict(p))


@router.put("/{plan_id}")
def update_plan(plan_id: int, body: PlanUpdate, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    p = _get_owned(db, plan_id, user.id)
    if not p:
        return fail("计划不存在", code=404)
    try:
        data = body.model_dump(exclude_unset=True)
        if "direction" in data and data["direction"] not in ("buy", "hold", "reduce", "sell"):
            return fail("direction 必须为 buy|hold|reduce|sell")
        if "status" in data and data["status"] not in ("draft", "active", "done", "cancelled"):
            return fail("status 必须为 draft|active|done|cancelled")
        for k, v in data.items():
            setattr(p, k, v)
        db.commit()
        db.refresh(p)
        return ok(_to_dict(p), msg="计划已更新")
    except Exception as e:
        db.rollback()
        return fail(f"更新计划失败：{e}")


@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = _get_owned(db, plan_id, user.id)
    if not p:
        return fail("计划不存在", code=404)
    try:
        db.delete(p)
        db.commit()
        return ok(None, msg="计划已删除")
    except Exception as e:
        db.rollback()
        return fail(f"删除计划失败：{e}")


@router.post("/from-analysis/{analysis_id}")
def plan_from_analysis(analysis_id: int, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    """读取分析 decision JSON，映射生成 draft 计划（归属当前用户）"""
    ana = db.query(Analysis).filter(Analysis.id == analysis_id,
                                    Analysis.user_id == user.id).first()
    if not ana:
        return fail("分析记录不存在", code=404)
    if not ana.decision:
        return fail("该分析尚无决策结论，无法生成计划")
    try:
        decision = json.loads(ana.decision)
    except Exception:
        return fail("分析决策数据解析失败")

    target = decision.get("target_price")
    action = (decision.get("action") or "hold").lower()
    if action not in ("buy", "hold", "reduce", "sell"):
        action = "hold"
    try:
        target = float(target) if target is not None else None
    except (TypeError, ValueError):
        target = None

    # 按任务书规则映射：entry=target*0.97，stop=target*0.93，risk_pct=0.01
    entry = round(target * 0.97, 2) if target else None
    stop = round(target * 0.93, 2) if target else None

    try:
        p = Plan(
            user_id=user.id,
            analysis_id=ana.id,
            code=ana.code,
            direction=action,
            entry_price=entry,
            stop_price=stop,
            target_price=round(target, 2) if target else None,
            risk_pct=0.01,
            note=(decision.get("summary") or "")[:500] or None,
            status="draft",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return ok(_to_dict(p), msg="已根据分析结论生成草稿计划。本系统仅用于学习研究，不构成投资建议")
    except Exception as e:
        db.rollback()
        return fail(f"生成计划失败：{e}")

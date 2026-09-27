# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""分析接口：发起 / 详情(含事件列表) / 历史列表"""
import json
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ok, fail, get_current_user
from app.models import Analysis, AnalysisEvent, User, Stock
from app.services.analysis_runner import start_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])

ALLOWED_VARIANTS = {"default", "conservative", "aggressive"}


def _analysis_dict(a: Analysis, with_events: bool = False, events=None):
    try:
        decision = json.loads(a.decision) if a.decision else None
    except Exception:
        decision = None
    data = {
        "id": a.id, "code": a.code, "status": a.status,
        "params": json.loads(a.params) if a.params else {},
        "decision": decision,
        "report_md": a.report_md,
        "error": a.error,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "finished_at": a.finished_at.isoformat() if a.finished_at else None,
    }
    if with_events:
        data["events"] = events or []
    return data


def _event_dict(e: AnalysisEvent):
    return {"seq": e.seq, "agent": e.agent_name, "kind": e.kind, "content": e.content,
            "created_at": e.created_at.isoformat() if e.created_at else None}


@router.post("/start")
def start(payload: dict = Body(...),
          db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    """发起分析：{code, variant?} -> {analysis_id}"""
    try:
        code = str(payload.get("code", "")).strip()
        variant = str(payload.get("variant", "default")).strip() or "default"
        if not code:
            return fail("缺少股票代码")
        if variant not in ALLOWED_VARIANTS:
            variant = "default"
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return fail(f"未找到股票 {code}，请先检索或刷新数据源")

        analysis = Analysis(user_id=user.id, code=code, status="pending",
                            params=json.dumps({"variant": variant}, ensure_ascii=False))
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        start_analysis(analysis.id, code, variant)  # 异步线程执行
        return ok({"analysis_id": analysis.id})
    except Exception as e:
        db.rollback()
        return fail(f"发起分析失败：{e}")


@router.get("/{analysis_id}")
def detail(analysis_id: int,
           db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    """分析详情 + 已产生事件列表（用于SSE断线重放/刷新补全）"""
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id,
                                             Analysis.user_id == user.id).first()
        if not analysis:
            return fail("分析不存在或无权访问", code=404)
        events = (db.query(AnalysisEvent)
                  .filter(AnalysisEvent.analysis_id == analysis_id)
                  .order_by(AnalysisEvent.seq.asc()).all())
        return ok(_analysis_dict(analysis, with_events=True,
                                 events=[_event_dict(e) for e in events]))
    except Exception as e:
        return fail(f"查询失败：{e}")


@router.get("")
def history(db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    """当前用户历史分析列表（按时间倒序，最多200条）"""
    try:
        rows = (db.query(Analysis)
                .filter(Analysis.user_id == user.id)
                .order_by(Analysis.id.desc()).limit(200).all())
        return ok([_analysis_dict(a) for a in rows])
    except Exception as e:
        return fail(f"查询失败：{e}")

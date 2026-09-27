# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""选股筛选路由：按 PE/PB 区间与市场过滤 Stock 表

本系统仅用于学习研究，不构成投资建议。
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, ok, fail
from app.models import Stock

router = APIRouter(prefix="/screening", tags=["screening"])


class ScreeningReq(BaseModel):
    min_pe: Optional[float] = None
    max_pe: Optional[float] = None
    min_pb: Optional[float] = None
    max_pb: Optional[float] = None
    markets: Optional[list[str]] = None
    limit: int = Field(default=50, ge=1, le=500)


def _ensure_stocks(db: Session) -> None:
    """Stock 表为空时，尝试从数据源（默认 mock）回填，保证筛选开箱可用"""
    try:
        if db.query(Stock).count() > 0:
            return
        from app.services.datasources.manager import get_source
        src = get_source()
        for item in src.list_stocks():
            db.add(Stock(
                code=item.get("code"), name=item.get("name"),
                market=item.get("market"), industry=item.get("industry"),
                currency=item.get("currency"), pe=item.get("pe"),
                pb=item.get("pb"), price=item.get("price"),
            ))
        db.commit()
    except Exception:
        db.rollback()


def _to_dict(s: Stock) -> dict:
    return {
        "code": s.code, "name": s.name, "market": s.market,
        "industry": s.industry,
        "pe": round(s.pe, 2) if s.pe is not None else None,
        "pb": round(s.pb, 2) if s.pb is not None else None,
        "price": round(s.price, 2) if s.price is not None else None,
    }


@router.post("/run")
def run_screening(req: ScreeningReq, db: Session = Depends(get_db),
                  _user=Depends(get_current_user)):
    """按条件筛选股票，返回命中列表"""
    try:
        _ensure_stocks(db)
        q = db.query(Stock)
        if req.min_pe is not None:
            q = q.filter(Stock.pe >= req.min_pe)
        if req.max_pe is not None:
            q = q.filter(Stock.pe <= req.max_pe)
        if req.min_pb is not None:
            q = q.filter(Stock.pb >= req.min_pb)
        if req.max_pb is not None:
            q = q.filter(Stock.pb <= req.max_pb)
        if req.markets:
            markets = [m.upper() for m in req.markets]
            q = q.filter(Stock.market.in_(markets))
        rows = q.order_by(Stock.code).limit(req.limit).all()
        return ok([_to_dict(s) for s in rows])
    except Exception as e:  # 统一错误包装
        return fail(f"筛选失败: {e}")

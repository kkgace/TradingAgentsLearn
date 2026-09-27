# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""股票查询路由：搜索 / 快照 / 列表，并把数据源数据 upsert 进 Stock 表缓存。"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ok, fail, get_current_user
from app.models import Stock
from app.services.datasources.manager import get_source

router = APIRouter(prefix="/stocks", tags=["stocks"])


def _upsert_stocks(db: Session, rows: list[dict]) -> None:
    """把数据源返回的股票记录 upsert 进 Stock 表（按 code 幂等）"""
    try:
        for r in rows:
            code = (r.get("code") or "").strip()
            if not code:
                continue
            st = db.query(Stock).filter(Stock.code == code).first()
            if st is None:
                st = Stock(code=code)
                db.add(st)
            st.name = r.get("name")
            st.market = r.get("market") or "CN"
            st.industry = r.get("industry")
            st.currency = r.get("currency") or "CNY"
            st.pe = r.get("pe")
            st.pb = r.get("pb")
            st.price = r.get("price")
            st.updated_at = datetime.now()
        db.commit()
    except Exception:
        db.rollback()  # 写库失败不影响查询返回


def _to_dict(s: Stock) -> dict:
    return {
        "code": s.code, "name": s.name, "market": s.market,
        "industry": s.industry, "currency": s.currency,
        "pe": s.pe, "pb": s.pb, "price": s.price,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("/search")
def search_stocks(q: str = "", market: str | None = None,
                  db: Session = Depends(get_db), _=Depends(get_current_user)):
    try:
        rows = get_source().search(q, market)
        _upsert_stocks(db, rows)
        return ok(rows)
    except Exception as e:
        return fail(f"股票搜索失败：{e}")


@router.get("/list")
def list_stocks(db: Session = Depends(get_db), _=Depends(get_current_user)):
    try:
        rows = get_source().list_stocks()
        _upsert_stocks(db, rows)
        return ok(rows)
    except Exception as e:
        return fail(f"股票列表获取失败：{e}")


@router.get("/{code}/quote")
def get_quote(code: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    try:
        row = get_source().get_quote(code)
        if row is None:
            return fail(f"未找到股票：{code}", code=404)
        _upsert_stocks(db, [row])
        return ok(row)
    except Exception as e:
        return fail(f"行情查询失败：{e}")

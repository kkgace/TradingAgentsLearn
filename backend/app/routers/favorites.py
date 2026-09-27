# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""自选股路由：GET /favorites、POST /favorites（幂等）、DELETE /favorites/{id}、GET /favorites/groups"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, ok, fail
from app.models import Favorite, Stock, User

router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteCreate(BaseModel):
    code: str
    group_name: Optional[str] = None


def _serialize(f: Favorite, stock: Stock | None = None) -> dict:
    """序列化自选股，附带股票基本信息（若 Stock 表存在记录）"""
    return {
        "id": f.id,
        "code": f.code,
        "group_name": f.group_name,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "name": stock.name if stock else None,
        "market": stock.market if stock else None,
        "industry": stock.industry if stock else None,
        "price": stock.price if stock else None,
        "pe": stock.pe if stock else None,
        "pb": stock.pb if stock else None,
    }


@router.get("")
def list_favorites(
    group: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户自选股列表（可选按分组过滤），按创建时间倒序"""
    try:
        q = db.query(Favorite).filter(Favorite.user_id == user.id)
        if group:
            q = q.filter(Favorite.group_name == group)
        favs = q.order_by(Favorite.created_at.desc(), Favorite.id.desc()).all()
        codes = {f.code for f in favs}
        stocks = {s.code: s for s in db.query(Stock).filter(Stock.code.in_(codes)).all()} if codes else {}
        return ok([_serialize(f, stocks.get(f.code)) for f in favs])
    except Exception as e:
        return fail(f"查询自选股失败: {e}")


@router.post("")
def add_favorite(
    body: FavoriteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加自选股；同用户同代码同分组重复添加时幂等返回已有记录"""
    try:
        code = (body.code or "").strip()
        if not code:
            return fail("股票代码不能为空")
        group_name = (body.group_name or "默认").strip() or "默认"
        existing = (
            db.query(Favorite)
            .filter(Favorite.user_id == user.id, Favorite.code == code,
                    Favorite.group_name == group_name)
            .first()
        )
        if existing:
            stock = db.query(Stock).filter(Stock.code == code).first()
            return ok(_serialize(existing, stock), msg="已存在于自选股")
        fav = Favorite(user_id=user.id, code=code, group_name=group_name)
        db.add(fav)
        db.commit()
        db.refresh(fav)
        stock = db.query(Stock).filter(Stock.code == code).first()
        return ok(_serialize(fav, stock), msg="已加入自选股")
    except Exception as e:
        db.rollback()
        return fail(f"添加自选股失败: {e}")


@router.delete("/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除自选股（仅限当前用户所有）"""
    try:
        fav = (
            db.query(Favorite)
            .filter(Favorite.id == favorite_id, Favorite.user_id == user.id)
            .first()
        )
        if not fav:
            return fail("自选股不存在")
        db.delete(fav)
        db.commit()
        return ok({"id": favorite_id}, msg="已删除")
    except Exception as e:
        db.rollback()
        return fail(f"删除自选股失败: {e}")


@router.get("/groups")
def list_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户的自选分组列表（含各组数量）"""
    try:
        rows = (
            db.query(Favorite.group_name)
            .filter(Favorite.user_id == user.id)
            .all()
        )
        counts: dict[str, int] = {}
        for (name,) in rows:
            name = name or "默认"
            counts[name] = counts.get(name, 0) + 1
        return ok([{"name": k, "count": v} for k, v in sorted(counts.items())])
    except Exception as e:
        return fail(f"查询分组失败: {e}")

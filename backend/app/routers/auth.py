# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""认证路由：注册 / 登录 / 当前用户，前缀 /auth"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_token, get_current_user, ok, fail,
)
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterReq(BaseModel):
    username: str
    password: str


class LoginReq(BaseModel):
    username: str
    password: str


def _user_info(u: User) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role}


@router.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    """注册：校验用户名重复，密码哈希入库"""
    try:
        username = (req.username or "").strip()
        if not username or not req.password:
            return fail("用户名与密码不能为空")
        if len(req.password) < 6:
            return fail("密码长度至少 6 位")
        exists = db.query(User).filter(User.username == username).first()
        if exists:
            return fail("用户名已被注册")
        user = User(username=username, password_hash=hash_password(req.password), role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
        return ok({"id": user.id, "username": user.username}, msg="注册成功")
    except Exception as e:
        db.rollback()
        return fail(f"注册失败：{e}")


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    """登录：校验密码，签发 JWT"""
    try:
        user = db.query(User).filter(User.username == (req.username or "").strip()).first()
        if not user or not user.is_active or not verify_password(req.password, user.password_hash):
            return fail("用户名或密码错误")
        token = create_token(user.id, user.username)
        return ok({"token": token, "user": _user_info(user)})
    except Exception as e:
        return fail(f"登录失败：{e}")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """返回当前登录用户信息"""
    return ok(_user_info(user))

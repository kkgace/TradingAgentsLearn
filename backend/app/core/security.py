# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd_ctx.verify(p, hashed)

def create_token(user_id: int, username: str) -> str:
    payload = {"sub": str(user_id), "name": username,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    from app.models import User
    try:
        payload = jwt.decode(cred.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="无效或过期登录凭证")
    user = db.query(User).filter(User.id == uid, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user

def ok(data=None, msg: str = "ok"):
    return {"code": 0, "data": data, "msg": msg}

def fail(msg: str, code: int = 1):
    return {"code": code, "data": None, "msg": msg}

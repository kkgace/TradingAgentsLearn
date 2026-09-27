# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""运行时应用设置：AppSetting 表的 JSON 读写（界面配置存储）。

约定：key 对应一个 JSON 对象；删除记录 = 清除覆盖（回退 .env/内置默认）。
"""
import json
import logging

from sqlalchemy.orm import Session

from app.models import AppSetting

logger = logging.getLogger(__name__)

# 数据源覆盖配置的键（值形如 {"tushare_api":..., "tushare_token":..., "tushare_codes":...}）
DATASOURCE_KEY = "datasource"


def get_setting(db: Session, key: str) -> dict | None:
    """读取设置；不存在或 JSON 损坏返回 None"""
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if not row or not row.value:
            return None
        obj = json.loads(row.value)
        return obj if isinstance(obj, dict) else None
    except Exception as e:
        logger.warning("读取设置 %s 失败：%s", key, e)
        return None


def set_setting(db: Session, key: str, value: dict) -> None:
    """写入/更新设置（upsert）"""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    payload = json.dumps(value, ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=key, value=payload))
    db.commit()


def clear_setting(db: Session, key: str) -> bool:
    """删除设置记录（回退 .env/默认）；返回是否删除了记录"""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True

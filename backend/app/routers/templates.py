# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""提示词模板路由：查询 / 编辑（版本自增）/ 版本信息"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ok, fail, get_current_user
from app.models import PromptTemplate

# 导入 worker.bootstrap 以触发 ensure_default_templates()（幂等），保证路由可用时模板已就绪
from app.worker import bootstrap  # noqa: F401

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateIn(BaseModel):
    content: str
    is_active: Optional[bool] = None


def _to_dict(t: PromptTemplate) -> dict:
    return {
        "id": t.id,
        "agent_name": t.agent_name,
        "variant": t.variant,
        "content": t.content,
        "version": t.version,
        "is_active": t.is_active,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("")
def list_templates(agent: Optional[str] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    """模板列表，可按 agent 名过滤"""
    try:
        q = db.query(PromptTemplate)
        if agent:
            q = q.filter(PromptTemplate.agent_name == agent)
        items = q.order_by(PromptTemplate.agent_name, PromptTemplate.variant,
                           PromptTemplate.id).all()
        return ok([_to_dict(t) for t in items])
    except Exception as e:
        return fail(f"查询模板失败：{e}")


@router.put("/{template_id}")
def update_template(template_id: int, body: TemplateIn, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    """编辑模板内容：version 自增（保留旧行为即可，不保留历史快照）"""
    t = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not t:
        return fail("模板不存在", code=404)
    try:
        if not body.content or not body.content.strip():
            return fail("模板内容不能为空")
        t.content = body.content
        if body.is_active is not None:
            t.is_active = body.is_active
        t.version = (t.version or 1) + 1
        db.commit()
        db.refresh(t)
        return ok(_to_dict(t), msg="模板已更新，版本号 +1")
    except Exception as e:
        db.rollback()
        return fail(f"更新模板失败：{e}")


@router.get("/{template_id}/versions")
def template_versions(template_id: int, db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    """返回该模板当前版本信息（v3.0 仅保留当前版本，不存历史快照）"""
    t = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not t:
        return fail("模板不存在", code=404)
    return ok({
        "id": t.id,
        "agent_name": t.agent_name,
        "variant": t.variant,
        "current_version": t.version,
        "is_active": t.is_active,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "history": [],  # 历史版本未持久化，仅版本号回溯可见
    })

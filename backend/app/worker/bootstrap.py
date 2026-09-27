# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""启动引导：把 13 个 Agent 的内置提示词模板写入 prompt_templates 表（幂等）"""
import logging

from app.core.database import SessionLocal
from app.models import PromptTemplate
from app.agents.default_templates import DEFAULT_TEMPLATES

logger = logging.getLogger(__name__)


def ensure_default_templates() -> int:
    """遍历 13 个 agent × (default, conservative)，缺记录则从内置模板导入。

    自行创建 Session（可能被请求线程之外的启动/调度线程调用），幂等可重复执行。
    返回新写入的模板条数。
    """
    db = SessionLocal()
    inserted = 0
    try:
        for agent_name, variants in DEFAULT_TEMPLATES.items():
            for variant, content in variants.items():
                exists = db.query(PromptTemplate).filter(
                    PromptTemplate.agent_name == agent_name,
                    PromptTemplate.variant == variant,
                ).first()
                if exists:
                    continue
                db.add(PromptTemplate(
                    agent_name=agent_name,
                    variant=variant,
                    content=content,
                    version=1,
                    is_active=True,
                ))
                inserted += 1
        db.commit()
        if inserted:
            logger.info("已导入内置提示词模板 %d 条", inserted)
    except Exception as e:
        db.rollback()
        logger.warning("导入内置提示词模板失败：%s", e)
    finally:
        db.close()
    return inserted

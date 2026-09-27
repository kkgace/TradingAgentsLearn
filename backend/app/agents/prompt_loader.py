# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""提示词加载：优先 PromptTemplate 表（variant > 用户默认 active），兜底内置模板"""
from sqlalchemy.orm import Session

from app.models import PromptTemplate
from .default_templates import DEFAULT_TEMPLATES

# 特殊处理不再存在的模板变量，默认值
DEFAULT_VARIANT = "default"

def load_prompt(db: Session, agent_name: str, variant: str = DEFAULT_VARIANT) -> str:
    """按 variant 查最新启用模板；找不到则回退默认variant，兜底内置模板"""
    try:
        # 1) 指定 variant 的最新启用模板
        tpl = (db.query(PromptTemplate)
               .filter(PromptTemplate.agent_name == agent_name,
                       PromptTemplate.variant == variant,
                       PromptTemplate.is_active == True)  # noqa: E712
               .order_by(PromptTemplate.version.desc()).first())
        # 2) 回退 default variant
        if tpl is None and variant != DEFAULT_VARIANT:
            tpl = (db.query(PromptTemplate)
                   .filter(PromptTemplate.agent_name == agent_name,
                           PromptTemplate.variant == DEFAULT_VARIANT,
                           PromptTemplate.is_active == True)  # noqa: E712
                   .order_by(PromptTemplate.version.desc()).first())
        if tpl:
            return tpl.content
    except Exception:
        pass  # 表不存在或查询异常时直接兜底
    # 3) 内置模板兜底
    agent = DEFAULT_TEMPLATES.get(agent_name, {})
    return agent.get(variant) or agent.get(DEFAULT_VARIANT) or f"你是{agent_name}智能体，输出中文分析。本系统仅用于学习研究，不构成投资建议。"

# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""13 Agent 串行编排：每步调 LLM -> 写 AnalysisEvent -> 推 SSE；最后由 decision 生成器
消费辩论结论输出结构化 JSON 决策（解析失败时关键词启发式兜底），生成 Markdown 报告"""
import json
import logging
import re

from sqlalchemy.orm import Session

from app.models import Stock, AnalysisEvent
from app.services.llm import llm_client
from app.services.sse_bus import bus
from .prompt_loader import load_prompt

logger = logging.getLogger(__name__)

# (agent_name, kind) 13 步固定顺序
PIPELINE: list[tuple[str, str]] = [
    ("fundamentals", "analyst"),
    ("market", "analyst"),
    ("news", "analyst"),
    ("social_media", "analyst"),
    ("bull", "researcher"),
    ("bear", "researcher"),
    ("research_manager", "manager"),
    ("trader", "trader"),
    ("conservative_debator", "debator"),
    ("neutral_debator", "debator"),
    ("aggressive_debator", "debator"),
    ("risk_manager", "manager"),
    ("final_summary", "manager"),
]


def _stock_brief(stock: Stock | None, code: str) -> str:
    """股票基础信息片段，注入 user 提示"""
    if not stock:
        return f"股票代码：{code}（基础数据缺失）"
    return (f"股票：{stock.name}({stock.code}) 市场:{stock.market} 行业:{stock.industry} "
            f"价格:{stock.price} PE:{stock.pe} PB:{stock.pb}")


# ---------------- 决策生成：LLM JSON 优先，关键词启发式兜底 ----------------

_ACTIONS = ("buy", "hold", "reduce", "sell")
# 启发式兜底时各 action 的目标价倍数与基准风险分
_TARGET_MULT = {"buy": 1.08, "hold": 1.05, "reduce": 0.98, "sell": 0.95}
_RISK_BASE = {"buy": 0.45, "hold": 0.50, "reduce": 0.55, "sell": 0.60}

BULL_KW = ("看多", "买入", "增持", "上涨", "突破", "强势", "机会")
BEAR_KW = ("看空", "卖出", "减持", "下跌", "止损", "回避")


def _extract_json_object(text: str) -> dict | None:
    """从 LLM 输出中容忍式提取 JSON 对象（允许前后缀杂讯/代码围栏）；失败返回 None"""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _sanitize_decision(raw: dict | None, base_price: float) -> dict | None:
    """清洗决策 JSON：action 必须合法；数值裁剪到 sane 区间；不合法返回 None"""
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action", "")).strip().lower()
    if action not in _ACTIONS:
        return None
    try:
        target = float(raw.get("target_price"))
        if not target > 0:
            raise ValueError
    except (TypeError, ValueError):
        target = base_price * _TARGET_MULT[action]
    conf = _clamp_unit(raw.get("confidence"), 0.55)
    risk = _clamp_unit(raw.get("risk_score"), _RISK_BASE[action])
    summary = str(raw.get("summary") or "")[:300]
    return {"action": action, "target_price": round(target, 2),
            "confidence": conf, "risk_score": risk, "summary": summary}


def _clamp_unit(value, default: float) -> float:
    """把数值裁剪进 [0,1]；非法取默认值"""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return round(min(1.0, max(0.0, x)), 2)


def _fallback_decision(outputs: list[str], base_price: float) -> dict:
    """LLM 未给出合法 JSON 时的确定性兜底：对全部 Agent 输出做关键词评分推导决策"""
    joined = "\n".join(outputs)
    score = (sum(joined.count(k) for k in BULL_KW)
             - sum(joined.count(k) for k in BEAR_KW))
    if score >= 3:
        action = "buy"
    elif score <= -3:
        action = "sell"
    else:
        action = "hold"
    confidence = round(min(0.85, 0.50 + abs(score) * 0.05), 2)
    summary = (f"基于 {len(outputs)} 个 Agent 输出的关键词评分（{score:+d}）推导的"
               f"示例性结论，仅供参考。")
    return {"action": action,
            "target_price": round(base_price * _TARGET_MULT[action], 2),
            "confidence": confidence,
            "risk_score": _RISK_BASE[action],
            "summary": summary}


def run_pipeline(db: Session, analysis_id: int, code: str, variant: str = "default") -> dict:
    """串行执行 13 Agent；返回 {"decision": dict, "report_md": str}"""
    topic = f"analysis:{analysis_id}"
    stock = db.query(Stock).filter(Stock.code == code).first()
    brief = _stock_brief(stock, code)
    base_price = float(stock.price) if stock and stock.price else 10.0

    upstream: list[str] = []     # 上游摘要（逐步累积，供后续 Agent 参考）
    contents: list[tuple[str, str]] = []   # (agent_name, 完整输出)，供决策生成器消费
    report_parts: list[str] = [f"# {code} 多智能体分析报告",
                               "",
                               "> 本系统仅用于学习研究，不构成投资建议。", ""]
    decision: dict = {}

    for seq, (agent_name, kind) in enumerate(PIPELINE, start=1):
        system = load_prompt(db, agent_name, variant)
        upstream_text = "\n".join(f"- {s}" for s in upstream[-6:]) or "（无上游输出）"
        user = f"{brief}\n\n上游结论摘要：\n{upstream_text}\n\n请以 {agent_name} 的角色给出本轮分析。"
        content = llm_client.chat(system, user)

        # 写事件并推送 SSE
        ev = AnalysisEvent(analysis_id=analysis_id, seq=seq, agent_name=agent_name,
                           kind=kind, content=content)
        db.add(ev)
        db.commit()
        bus.publish(topic, {"type": "agent", "seq": seq, "agent": agent_name,
                            "kind": kind, "content": content})

        upstream.append(f"{agent_name}: {content[:120]}")
        contents.append((agent_name, content))
        report_parts.append(f"## {seq}. {agent_name}（{kind}）")
        report_parts.append(content)
        report_parts.append("")

    # 决策生成：以 decision 模板再调一次 LLM（要求严格 JSON），消费辩论结论；
    # 解析/清洗失败时用关键词启发式兜底（MOCK 模式即走此路径，结果确定性）
    decision_system = load_prompt(db, "decision", variant)
    digest = "\n\n".join(f"{n}：{c[:600]}" for n, c in contents[-4:])   # trader 起的末 4 步
    decision_user = (f"{brief}\n\n关键结论摘录：\n{digest}\n\n"
                     f"请基于以上结论只输出一个决策 JSON 对象。")
    raw = llm_client.chat(decision_system, decision_user)
    decision = _sanitize_decision(_extract_json_object(raw), base_price)
    if decision is None:
        decision = _fallback_decision([c for _, c in contents], base_price)
        logger.info("analysis=%s 决策 JSON 解析失败，已用关键词启发式兜底：action=%s",
                    analysis_id, decision["action"])
    else:
        logger.info("analysis=%s 决策由 LLM JSON 生成：action=%s",
                    analysis_id, decision["action"])
    db.add(AnalysisEvent(analysis_id=analysis_id, seq=len(PIPELINE) + 1,
                         agent_name="decision", kind="decision",
                         content=json.dumps(decision, ensure_ascii=False)))
    db.commit()
    bus.publish(topic, {"type": "decision", "decision": decision})

    report_parts.append("## 最终决策")
    report_parts.append(f"- 操作：{decision['action']}")
    report_parts.append(f"- 目标价：{decision['target_price']:.2f}")
    report_parts.append(f"- 置信度：{decision['confidence']}")
    report_parts.append(f"- 风险评分：{decision['risk_score']}")
    if decision.get("summary"):
        report_parts.append(f"- 摘要：{decision['summary']}")
    report_parts.append("")
    report_md = "\n".join(report_parts)

    bus.publish(topic, {"type": "done", "analysis_id": analysis_id})
    return {"decision": decision, "report_md": report_md}

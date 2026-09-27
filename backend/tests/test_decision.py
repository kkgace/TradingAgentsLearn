# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""决策生成测试：JSON 容错提取、字段清洗、关键词启发式兜底、MOCK 全链路"""
from app.agents.graph import (PIPELINE, _extract_json_object, _fallback_decision,
                              _sanitize_decision, run_pipeline)
from app.models import Analysis, AnalysisEvent, Stock


# ---------- JSON 容错提取 ----------

def test_extract_json_clean():
    assert _extract_json_object('{"action": "buy"}') == {"action": "buy"}


def test_extract_json_with_noise_and_fence():
    text = '结论如下：\n```json\n{"action": "hold", "confidence": 0.5}\n```\n请查收。'
    assert _extract_json_object(text)["action"] == "hold"


def test_extract_json_invalid_returns_none():
    assert _extract_json_object("没有任何 JSON") is None
    assert _extract_json_object("[1, 2]") is None      # 只接受对象
    assert _extract_json_object('{"broken": ') is None
    assert _extract_json_object("") is None


# ---------- 字段清洗 ----------

def test_sanitize_decision_accepts_and_normalizes():
    d = _sanitize_decision({"action": "BUY", "target_price": 12.34,
                            "confidence": 0.7, "risk_score": 0.4, "summary": "s"}, 10.0)
    assert d == {"action": "buy", "target_price": 12.34,
                 "confidence": 0.7, "risk_score": 0.4, "summary": "s"}


def test_sanitize_decision_clamps_units_and_defaults_target():
    d = _sanitize_decision({"action": "hold", "confidence": 5, "risk_score": -1}, 10.0)
    assert d["confidence"] == 1.0
    assert d["risk_score"] == 0.0
    assert d["target_price"] == 10.5            # 缺目标价按基准 *1.05


def test_sanitize_decision_rejects_bad_action_or_payload():
    assert _sanitize_decision({"action": "yolo"}, 10.0) is None
    assert _sanitize_decision(None, 10.0) is None
    assert _sanitize_decision({"confidence": 0.5}, 10.0) is None   # 无 action


# ---------- 关键词启发式兜底 ----------

def test_fallback_decision_bullish():
    outs = ["趋势强势突破，看多并建议买入增持"] * 5
    assert _fallback_decision(outs, 100.0)["action"] == "buy"


def test_fallback_decision_bearish():
    outs = ["趋势下跌，看空并建议卖出减持回避"] * 5
    assert _fallback_decision(outs, 100.0)["action"] == "sell"


def test_fallback_decision_neutral_hold():
    d = _fallback_decision(["中性内容，不含方向词"], 100.0)
    assert d["action"] == "hold"
    assert d["target_price"] == 105.0
    assert d["confidence"] == 0.5


# ---------- MOCK 全链路：13 Agent + 决策事件 + 报告 ----------

def test_run_pipeline_mock_end_to_end(db, user):
    db.add(Stock(code="600519", name="贵州茅台", market="CN", industry="白酒",
                 currency="CNY", pe=22.5, pb=8.6, price=1620.0))
    analysis = Analysis(user_id=user.id, code="600519", status="pending", params="{}")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    result = run_pipeline(db, analysis.id, "600519")

    events = (db.query(AnalysisEvent)
              .filter(AnalysisEvent.analysis_id == analysis.id)
              .order_by(AnalysisEvent.seq).all())
    # 13 个 Agent 事件 + 1 个 decision 事件
    assert len(events) == len(PIPELINE) + 1
    assert [e.agent_name for e in events[:len(PIPELINE)]] == [n for n, _ in PIPELINE]
    assert events[-1].kind == "decision"

    decision = result["decision"]
    assert decision["action"] in ("buy", "hold", "reduce", "sell")
    # MOCK 文本不含方向关键词 -> 启发式稳定判 hold，目标价 = 现价 *1.05
    assert decision["action"] == "hold"
    assert decision["target_price"] == round(1620.0 * 1.05, 2)
    assert 0.0 <= decision["confidence"] <= 1.0
    assert 0.0 <= decision["risk_score"] <= 1.0

    report = result["report_md"]
    assert report.startswith("# 600519 多智能体分析报告")
    assert "最终决策" in report and "摘要" in report
    assert "不构成投资建议" in report

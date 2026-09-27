# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""LLM 抽象层测试：MOCK 确定性输出、真实调用失败时的降级标记"""
from app.services.llm import LLMClient


def test_mock_mode_when_no_credentials():
    c = LLMClient()
    assert c.mock is True            # 测试环境未配置 LLM 密钥


def test_mock_reply_deterministic_and_disclaimed():
    c = LLMClient()
    a = c.chat("你是测试智能体。", "某输入")
    b = c.chat("你是测试智能体。", "某输入")
    assert a == b                                    # 确定性：同输入同输出
    assert a.startswith("【模拟模式】")
    assert "不构成投资建议" in a


def test_mock_reply_echoes_agent_role():
    c = LLMClient()
    out = c.chat("你是 TradingAgents-Calv 学习平台中的基本面分析师。输出中文。", "输入")
    assert "基本面分析师" in out


class _Raiser:
    """模拟 openai 客户端任何属性访问都抛错的故障场景"""
    def __getattr__(self, name):
        raise RuntimeError("连接失败")


def test_llm_failure_returns_marked_degraded_output():
    c = LLMClient()
    c.mock = False                   # 强制走真实调用分支
    c._client = _Raiser()
    out = c.chat("系统提示", "用户提示")
    assert out.startswith("【LLM调用失败，以下为降级模拟内容】")
    assert "不构成投资建议" in out

# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""LLM 抽象：优先 OpenAI 兼容协议；未配置时进入确定性 MOCK 模式。
真实调用失败时记录日志并在降级内容前加显式标记，避免用户误以为是真实分析。"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.mock = not (settings.LLM_BASE_URL and settings.LLM_API_KEY)
        self._client = None
        if not self.mock:
            try:
                import openai
                self._client = openai.OpenAI(base_url=settings.LLM_BASE_URL,
                                             api_key=settings.LLM_API_KEY, timeout=120)
            except Exception as e:
                logger.warning("openai 客户端初始化失败，整系统退回 MOCK 模式：%s", e)
                self.mock = True

    def chat(self, system: str, user: str) -> str:
        if self.mock:
            return self._mock_reply(system, user)
        try:
            r = self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.3)
            return r.choices[0].message.content or ""
        except Exception as e:
            logger.warning("LLM 调用失败，本条降级为模拟输出：%s", e)
            return "【LLM调用失败，以下为降级模拟内容】" + self._mock_reply(system, user)

    def _mock_reply(self, system: str, user: str) -> str:
        # 确定性模拟输出：让每个 Agent 都有可读内容，全链路可演示
        agent = "智能体"
        for line in system.splitlines():
            if "你是" in line:
                agent = line.strip()[:40]
                break
        hint = (user or "").replace("\n", " ")[:80]
        return (f"【模拟模式】{agent} 已基于输入完成分析。关键输入摘要：{hint}…… "
                f"结论为示例性输出：综合判断中性偏谨慎，建议控制仓位、跟踪关键价格位，"
                f"并等待更多数据验证。本内容仅供学习研究，不构成投资建议。")

llm_client = LLMClient()

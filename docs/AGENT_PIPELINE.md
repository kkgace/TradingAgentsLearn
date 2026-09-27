<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
# 13 Agent 流水线说明（AGENT_PIPELINE）

> 本系统仅用于学习研究，不构成投资建议。

## 1. 执行顺序与职责

`backend/app/agents/graph.py` 的 `run_pipeline(db, analysis_id, code, variant)` **串行**执行以下 13 步：

| seq | agent_name | kind | 职责 |
|---|---|---|---|
| 1 | fundamentals | analyst | 基本面分析师：财务/估值（PE/PB）解读 |
| 2 | market | analyst | 行情分析师：价格走势与技术形态 |
| 3 | news | analyst | 新闻分析师：近期公告与新闻影响 |
| 4 | social_media | analyst | 社媒分析师：舆情与情绪面 |
| 5 | bull | researcher | 多头研究员：看多论证（辩论第 1 轮） |
| 6 | bear | researcher | 空头研究员：看空论证（辩论第 1 轮） |
| 7 | bull | researcher | 多头反驳（辩论第 2 轮） |
| 8 | bear | researcher | 空头反驳（辩论第 2 轮） |
| 9 | research_manager | manager | 研究经理：综合多空，形成研究结论 |
| 10 | trader | trader | 交易员：给出操作计划草案 |
| 11 | conservative_debator | debator | 保守派辩手：风险优先评估 |
| 12 | neutral_debator | debator | 中性辩手：平衡评估 |
| 13 | aggressive_debator | debator | 激进派辩手：收益优先评估 |

> 终审与汇总：`risk_manager` 风险评估 + `final_summary` 汇总在流水线收尾阶段输出 decision 与 Markdown 报告（模板字典中亦提供这两类模板）。

每一步均执行：**加载模板 → `LLMClient.chat(system, user)`（user 中拼接股票基础信息与上游摘要）→ 写入 `analysis_events` 表（seq 递增）→ `bus.publish("analysis:{id}", ...)` 推送 SSE**。

## 2. 提示词模板生效优先级

`prompt_loader.load_prompt(db, agent_name, variant)` 按以下优先级取模板：

```
请求参数指定 variant (分析时传入)
        │
        ▼ 未命中
用户设置（settings 表中的用户偏好）
        │
        ▼ 未命中
prompt_templates 表中 is_active 的默认模板
        │
        ▼ 未命中
app.agents.default_templates 内置模板（兜底，永不为空）
```

内置模板字典（`default_templates.py`）为 13 个 agent 各提供 `default` 与 `conservative` 两个变体；`worker/bootstrap.py` 启动时把缺失的内置模板落库。通过 `/api/templates` 编辑模板会 `version+1`。

## 3. SSE 事件格式

端点：`GET /sse/analysis/{analysis_id}`（需 JWT，token 走 query 传递）。通道：`analysis:{analysis_id}`。

### 3.1 agent 事件（每个 Agent 输出一条）

```json
{
  "type": "agent",
  "seq": 5,
  "agent": "bull",
  "kind": "researcher",
  "content": "多头观点：该公司护城河深厚……（Markdown 文本）"
}
```

### 3.2 decision 事件（最终决策 JSON）

```json
{
  "type": "decision",
  "analysis_id": 42,
  "code": "600519",
  "decision": {
    "action": "buy",
    "target_price": 1850.00,
    "confidence": 0.72,
    "risk_score": 0.35,
    "summary": "综合多空辩论与风险评审，建议小幅买入……"
  }
}
```

### 3.3 done 事件（流水线结束，前端应关闭连接）

```json
{ "type": "done", "analysis_id": 42, "status": "done" }
```

异常时分析状态置为 `failed` 并记录 error；前端可通过 `GET /api/analysis/{id}` 拉取全量事件列表（`analysis_events` 表即 SSE 的重放依据）。

## 4. Mock 模式

未配置 `LLM_API_KEY` 时自动进入 Mock 模式：`MockLLMClient` 返回确定性的中文教学示例内容，13 步按序照常落库与推送，保证离线全链路可演示。配置 OpenAI 兼容端点（`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`）后即切换真实模型。

## 5. 并发与线程注意

- 每次分析由 `analysis_runner` 起一个后台 `threading.Thread`，**线程内自行新建 `SessionLocal` 并关闭**（SQLite，禁共享连接）。
- 金额保留 2 位小数；时间戳 ISO8601。

<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
# TradingAgents-Calv v3.0 架构说明

> 本系统仅用于学习研究，不构成投资建议。

## 1. 总体架构

```
┌────────────────────────────────────────────────────────────────┐
│                        浏览器 (Vue 3 SPA)                       │
│   Login / Dashboard / Screening / Favorites / Analysis(Detail) │
│   Plans / Triggers / Paper / Journal / Templates / Settings    │
│        axios(/api)        EventSource(/sse/analysis/:id)        │
└──────────────┬───────────────────────────┬─────────────────────┘
               │ HTTP/JSON {code,data,msg} │ SSE(text/event-stream)
┌──────────────▼─────────────┐   ┌─────────▼──────────────────────┐
│      FastAPI (Uvicorn)      │   │  sse_bus（进程内事件总线）      │
│  routers/                   │   │  analysis:{id} / triggers     │
│   auth stocks screening     │   └─────────▲──────────────────────┘
│   favorites analysis plans  │             │ publish
│   triggers paper journal    │   ┌─────────┴──────────────────────┐
│   templates reports         │   │  analysis_runner (Thread)      │
└──────┬───────────────┬──────┘   │   └─ agents/graph.py           │
       │               │          │      13 Agent 串行 Pipeline     │
       │               │          │      每步: prompt→LLM→event→SSE │
┌──────▼──────┐ ┌──────▼───────┐ └─────────▲──────────────────────┘
│ LLM 抽象层   │ │ 数据源抽象层  │           │ SessionLocal(线程内新建)
│ services/llm│ │ datasources/ │           │
│  OpenAI兼容  │ │  Mock(默认)   │           │
│  Mock 兜底   │ │  Tushare可选  │           │
└─────────────┘ └──────────────┘           │
                ┌───────────────────────────▼───────────────────┐
                │   SQLAlchemy(sync) + SQLite (data/calv.db)     │
                │ users/stocks/favorites/analyses/               │
                │ analysis_events/prompt_templates/plans/        │
                │ triggers/paper_*/journal_entries/settings      │
                └────────────────────────────────────────────────┘
        ┌────────────────────────────────────────────────────────┐
        │ worker/scheduler (APScheduler 线程): 触发器轮询          │
        │  命中 → paper_engine.place_order → bus.publish("triggers")│
        └────────────────────────────────────────────────────────┘
```

## 2. 核心数据流（学习闭环）

```
筛选(screening) ──▶ 分析(analysis:start) ──▶ 13 Agent 辩论(SSE 实时推送)
      │                                            │
      │                                            ▼
      │                                    decision JSON + report_md
      │                                            │
      │                          POST /plans/from-analysis/:id
      │                                            ▼
      │                                   交易计划 Plan(draft)
      │                                            │
      │                                   触发器 Trigger(on)
      │                                            │ scheduler 轮询价格命中
      │                                            ▼
      └──── 复盘 journal ◀── paper_orders/positions ◀── 模拟盘自动下单
```

## 3. 模块说明

| 模块 | 位置 | 职责 |
|---|---|---|
| main.py | backend/app | FastAPI 装配、CORS、路由注册、建表、SSE 端点、调度器启动 |
| core/ | backend/app/core | config(pydantic-settings)、database(engine/Session)、security(JWT/密码哈希) |
| routers/ | backend/app/routers | REST API，统一 `{code,data,msg}` 返回，JWT 保护 |
| agents/ | backend/app/agents | 13 Agent 模板(default_templates)、prompt_loader、graph 编排 |
| services/llm | backend/app/services/llm | LLMClient(OpenAI 兼容) + Mock 模式（无 key 自动降级，离线可跑） |
| services/datasources | backend/app/services/datasources | DataSourceBase / MockDataSource(默认，20 只确定性示例股) / TushareSource(可选，A 股日线) |
| services/sse_bus.py | backend/app/services | 进程内发布订阅总线，SSE 重放依据为 analysis_events 表 |
| services/analysis_runner.py | backend/app/services | 后台线程跑 Pipeline，更新 Analysis 状态 |
| services/paper_engine.py | backend/app/services | 模拟盘：多币种账户、佣金/印花税、持仓、已实现盈亏(折算 CNY) |
| worker/ | backend/app/worker | bootstrap(内置模板落库)、scheduler(触发器轮询) |

## 4. 扩展点

1. **新数据源**：继承 `datasources/base.py` 的 `DataSourceBase`（`list_stocks/get_quote/search`），在 `manager.py` 注册；导入失败自动降级 Mock。
2. **新 LLM 提供商**：实现 OpenAI 兼容协议即可，经环境变量 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` 切换；无 key 自动 Mock。
3. **新 Agent / 提示词变体**：向 `prompt_templates` 表插入 `(agent_name, variant)` 记录即可，无需改代码；模板优先级：请求参数指定 variant > 用户设置 > is_active 默认 > 内置模板。
4. **新触发器类型**：`triggers.type` 扩展枚举（现支持 price_above/price_below），scheduler 的判定函数按类型分支。
5. **新市场**：`paper_engine` 按代码前缀判定市场（6 位数字=CN、5 位=HK、字母=US），加新市场仅需扩展判定与汇率/费率表。
6. **前端新页面**：`router/index.ts` 注册路由 + `Layout.vue` 菜单项；API 经 `api/client.ts`（自动带 Bearer token、错误 toast）。

## 5. 部署形态

- **Docker**：`docker compose up --build`，frontend(nginx:80) 反代 `/api`、`/sse` 到 backend:8000（SSE 关 proxy_buffering）。
- **Ubuntu 裸机**：`scripts/deploy_ubuntu.sh`（python3.11 venv + npm build + nohup/systemd）。

## 6. 合规声明

本系统仅用于学习研究，不构成投资建议。模拟盘为虚拟资金，任何输出（含 decision、报告）均为 AI 生成的教学示例。

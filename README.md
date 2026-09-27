# TradingAgentsLearn 🎓

> **多智能体（13-Agent）股票分析学习平台** —— 筛选 → AI 辩论分析 → 交易计划 → 触发器 → 模拟盘 → 复盘，全链路学习闭环。
>
> ⚠️ **本系统仅用于学习研究，不构成任何投资建议。** 所有行情、分析结论与模拟盘数据均为教学演示内容，不代表对任何证券的推荐。

A 股 / 港股 / 美股 · FastAPI + Vue 3 + SQLite · 离线 MOCK 全流程可演示 · 支持自定义 Tushare 中转站

---

## ✨ 功能特性

- **🔁 全链路学习闭环**：估值筛选 → 13-Agent 辩论分析（SSE 实时可视化）→ 一键生成交易计划 → 价格触发器 → 模拟盘自动执行 → 复盘日记与统计。
- **🤖 13-Agent 串行辩论流水线**：4 位分析师（基本面/市场/新闻/社媒）→ 多空研究员对抗 → 研究经理 → 交易员 → 保守/中立/激进三辩手 → 风控经理 → 总结官，每个 Agent 的输出通过 SSE 逐条实时推送，前端时间线可视化。
- **🧠 决策真实化**：辩论结论注入决策生成器，由 LLM 输出结构化 JSON 决策（action / target_price / confidence / risk_score），容忍式解析 + 字段清洗，解析失败自动降级为确定性关键词启发式。
- **📈 数据源**：Tushare Pro HTTP API（A 股日线，支持**自定义中转站地址**）；内置 20 只确定性 Mock 数据（CN/HK/US），未配置 token 或调用失败自动降级，离线可完整演示。
- **⚙️ 界面在线配置**：中转站地址 / token / 股票池可在「系统设置」页修改，**保存即生效无需重启**；优先级：界面配置（数据库）> `.env` 环境变量 > 内置默认。
- **💹 模拟盘**：多币种账户（CNY/HKD/USD）、按市场区分佣金（A股万3 最低 5 元 / 港股卖出印花税 0.13% / 美股免佣）、持仓加权成本、已实现盈亏折算 CNY。
- **⏰ 触发器**：price_above / price_below 后台轮询（APScheduler），命中后自动按手数取整下单，计划闭环置 done。
- **📝 复盘与模板**：复盘日记 + 近 30 天统计；13+1 个 Agent 提示词模板可在线管理（default / conservative 变体）。
- **🔔 实时推送**：进程内 SSE 事件总线按订阅者各自的事件循环投递，支持断线后通过详情接口重放。

## 🏗️ 架构

```
┌─────────────┐      HTTP /api       ┌──────────────────────────────┐
│  Browser     │ ◄────────────────── │  FastAPI Backend (:8000)     │
│  Vue3 + EP  │  ◄─ SSE /sse ─────── │  ├ routers/  REST 接口        │
└─────▲───────┘                      │  ├ agents/   13-Agent 流水线   │
      │ nginx (frontend 容器 / 80)   │  ├ services/ llm(含MOCK)       │
      │  ├─ /        → 静态 SPA      │  │            datasources      │
      │  ├─ /api    → backend:8000   │  │            (Tushare/Mock)   │
      │  └─ /sse    → backend:8000   │  ├ worker/    触发器轮询(APScheduler)
      │                              │  └ SQLite  data/calv.db       │
      └── docker-compose: frontend + backend 两容器
```

## 🚀 快速开始

### Docker（推荐）

```bash
docker compose up --build
# 打开 http://localhost  注册账号即可使用
```

### Ubuntu 裸机

```bash
bash scripts/deploy_ubuntu.sh   # 建 venv、装依赖、npm build、生成 backend/.env 并启动
```

### 本地开发（前后端分离）

```bash
# 后端（默认 8000 端口被占用时可换端口）
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端（Vite 代理 /api、/sse 到后端；后端端口非 8000 时用 VITE_API_PORT 指定）
cd frontend && npm ci
VITE_API_PORT=8000 npm run dev   # 打开 http://localhost:5173
```

## ⚙️ 环境变量（backend/.env 或 compose environment）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `JWT_SECRET` | JWT 签名密钥 | 开发默认值（**部署请务必修改**） |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI 兼容协议接入；不配置则全系统进入 MOCK 模式 | 空（MOCK） |
| `TUSHARE_TOKEN` | Tushare Pro 接口令牌；配置后数据源切换为 Tushare（A 股日线） | 空（Mock 数据源） |
| `TUSHARE_API` | Tushare 接口地址，可改为自建中转站（需兼容 Tushare Pro HTTP 协议） | `http://api.tushare.pro` |
| `TUSHARE_CODES` | Tushare 股票池（逗号分隔 6 位代码） | 内置 10 只 A 股 |
| `ENABLE_SCHEDULER` | 是否启用触发器后台轮询 | `true` |
| `TRIGGER_POLL_SECONDS` | 触发器轮询间隔秒 | `30` |
| `DATABASE_URL` | SQLAlchemy 连接串 | `sqlite:///backend/data/calv.db` |

> Tushare 中转站地址、token 与股票池也可登录后在 **「系统设置」页** 在线修改（保存即生效，优先级高于 .env），并支持一键「测试连接」。

## 🔒 密钥与安全

- 本仓库**不包含任何真实密钥或 token**（已做全量扫描：代码、日志、历史提交）。
- 密钥只存在于两个地方：本地 **环境变量 / `backend/.env`**（已 gitignore），或登录后写入**应用数据库**的界面配置（`backend/data/` 整目录已 gitignore）。
- JWT 密钥、LLM 密钥、Tushare token 均支持环境变量注入；`backend/.env` 不会被提交。
- 运行时产物（SQLite 库、日志）一律不入库。

## 🤖 13-Agent 流水线

| 阶段 | Agent | 职责 |
| --- | --- | --- |
| 分析 | fundamentals / market / news / social_media | 基本面、技术面、新闻、社媒情绪 |
| 研究 | bull ↔ bear → research_manager | 多空对抗与综合裁决 |
| 计划 | trader | 方向、入场、止损、目标价 |
| 风控 | conservative / neutral / aggressive 辩手 → risk_manager | 三方风险辩论与终审 |
| 汇总 | final_summary → **decision** | 总结 + 结构化 JSON 决策 |

每个 Agent 的提示词支持 `default` / `conservative` 变体，可在「提示词模板」页管理与查看版本。

## 🧪 测试

```bash
cd backend && pip install -r requirements-dev.txt
pytest                                  # 66 个单元/集成测试（模拟盘、决策解析、调度闭环、SSE 总线、Tushare 数据源、设置接口）
python tests/smoke_e2e.py http://127.0.0.1:8123   # 端到端冒烟（需先以临时库启动服务）
```

测试环境强制封闭（`tests/conftest.py`）：临时 SQLite + 强制 MOCK 数据源，不依赖、不触碰任何宿主机密钥。

## 📁 目录结构

```
backend/
  app/
    main.py               # FastAPI 装配（CORS、路由、SSE、调度器）
    core/                 # 配置 / 数据库 / 安全(JWT)
    models.py             # SQLAlchemy 模型
    routers/              # auth/stocks/screening/favorites/analysis/plans/triggers/paper/journal/templates/reports/settings
    agents/               # 13-Agent 编排 + 提示词模板
    services/
      llm.py              # LLM 抽象（OpenAI 兼容 + MOCK 降级）
      datasources/        # DataSourceBase / Mock / Tushare(支持中转站) / manager
      paper_engine.py     # 模拟盘引擎
      sse_bus.py          # SSE 事件总线
      app_settings.py     # 界面配置存储
    worker/               # APScheduler 触发器轮询
  tests/                  # pytest 用例 + 端到端冒烟
frontend/
  src/
    views/                # 12 个页面（仪表盘/筛选/自选/分析/计划/触发器/模拟盘/复盘/模板/设置…）
    components/Layout.vue # 侧边栏 Admin 布局
    api/  stores/  router/
nginx/nginx.conf  docker-compose.yml  scripts/deploy_ubuntu.sh  spec/
```

## 📄 免责声明

1. 本系统为开源学习项目，仅用于教学与研究多智能体分析流程，**不构成任何投资建议**。
2. 系统中的行情、新闻、估值与 Agent 输出可能是模型生成或演示数据，不保证真实性、准确性、完整性。
3. 模拟盘撮合与盈亏统计仅用于训练复盘，与实际交易存在滑点、流动性、规则等重大差异。
4. 任何基于本系统内容作出真实投资决策所产生的后果，由使用者自行承担。

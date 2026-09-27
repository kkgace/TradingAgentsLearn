# TradingAgents-Calv v3.0 —— 共享开发规范（所有子代理必读）

> 本文件是所有编码子代理的唯一权威契约。任何与本文件冲突的自创方案都不允许。
> 项目根目录：`D:\work\TradingAgents-Calv`

## 0. 项目定位
多智能体 A 股/港股/美股 **学习用** 分析平台（教育用途，不构成投资建议）。v3.0 主题：
1. 学习闭环：筛选 → 分析（13 Agent 多智能体辩论，过程可视化）→ 交易计划 → 触发器 → 模拟盘执行 → 复盘；
2. Agent 可配置化：提示词模板（默认/保守/激进等多套）+ 版本管理；
3. AI 原生体验：SSE 实时推送 Agent 逐条输出、辩论时间线可视化。

## 1. 技术栈（固定，不得更换）
- 后端：Python 3.11 + FastAPI + Uvicorn + SQLAlchemy 2.x(sync) + SQLite（文件 `data/calv.db`，无需外部服务）+ `sse-starlette`（SSE 推送）。
- LLM：抽象层 `backend/app/services/llm/provider.py`，支持 OpenAI 兼容协议（环境变量 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`）；**未配置密钥时必须进入 MOCK 模式**（返回确定性假分析内容，保证全系统离线可跑）。
- 数据源：`backend/app/services/datasources/`，统一接口 `DataSourceBase`；实现 `MockDataSource`（内置 20 只示例股票确定性数据）为默认，`TushareSource`（可选，Tushare Pro HTTP API，A 股日线；配置 `TUSHARE_TOKEN` 启用，未覆盖代码与调用失败自动降级 Mock）。
- 前端：Vue 3 + TypeScript + Vite 5 + Element Plus + Pinia + Vue Router 4 + ECharts + axios。
- 部署：docker-compose（backend + frontend 两容器，frontend 用 nginx 并反代 `/api`、`/sse`）；另附 Ubuntu 裸机 `scripts/deploy_ubuntu.sh`。

## 2. 目录结构（固定）
```
backend/
  requirements.txt
  app/
    main.py                # FastAPI 装配（CORS、路由注册、启动建表）
    core/config.py         # pydantic-settings 配置
    core/database.py       # engine/session/get_db
    core/security.py       # JWT + 密码哈希
    models/                # SQLAlchemy 模型（每文件一类）
    schemas/               # pydantic 请求/响应
    routers/               # auth, stocks, screening, favorites, analysis, plans, triggers, paper, journal, templates, reports, settings
    agents/                # 13 Agent 工厂 + templates loader + graph 编排 + mock_llm
    services/
      llm/provider.py      # LLMClient（含 MockLLMClient）
      datasources/         # base.py, mock_source.py, tushare_source.py, manager.py
      sse_bus.py           # 进程内事件总线（analysis 进度/成交/触发）
    worker/scheduler.py    # APScheduler：触发器轮询、复盘提醒（同步实现，线程池）
frontend/
  package.json vite.config.ts tsconfig.json index.html
  src/
    main.ts  App.vue  router/index.ts  stores/  api/  views/  components/
nginx/nginx.conf
docker-compose.yml
backend/Dockerfile  frontend/Dockerfile
scripts/deploy_ubuntu.sh
```

## 3. 数据库模型（models/ 汇总，字段以 `models/__init__.py` 为准）
- `users`: id, username(uni), password_hash, role(user/admin), is_active, created_at
- `settings`: id, key(uni), value(JSON str)
- `stocks`: id, code(uni 如 600519), name, market(CN/HK/US), industry, currency, pe, pb, price, updated_at
- `favorites`: id, user_id, group_name, code, created_at（user_id+code+group 唯一）
- `analyses`: id, user_id, code, status(pending|running|done|failed), params(JSON), decision(JSON: action/target_price/confidence/risk_score), report_md(TEXT), created_at, finished_at
- `analysis_events`: id, analysis_id, seq, agent_name, kind(analyst|researcher|debator|manager|trader), content, created_at —— SSE 流式重放依据
- `prompt_templates`: id, agent_name, variant(default/conservative/aggressive/...), content, version, is_active
- `plans`: id, user_id, analysis_id, code, direction(buy/hold/reduce/sell), entry_price, stop_price, target_price, risk_pct, note, status(draft|active|done|cancelled), created_at
- `triggers`: id, user_id, plan_id, type(price_above|price_below|ma_cross), params(JSON), status(on|off|fired), fired_at
- `paper_accounts`: id, user_id(uni), cash_cny, cash_hkd, cash_usd, realized_pnl_cny
- `paper_orders`: id, user_id, plan_id?, code, market, side(buy/sell), qty, price, currency, commission, status(filled|rejected), reason, created_at
- `paper_positions`: id, user_id, code, market, qty, avg_cost, currency（user_id+code 唯一）
- `journal_entries`: id, user_id, plan_id?, title, content, pnl?, adherence_score?, created_at

## 4. REST API（前缀 `/api`，统一返回 `{code:int, data:any, msg:str}`，非 0 即错）
- `POST /api/auth/register` `POST /api/auth/login`（返回 JWT）`GET /api/auth/me`
- `GET /api/stocks/search?q=&market=` `GET /api/stocks/{code}/quotes`
- `GET/POST/DELETE /api/favorites`
- `POST /api/screening/run` body：`{min_pe?, max_pe?, min_pb?, max_pb?, markets:[], limit}` 返回命中股票列表
- `POST /api/analysis/start` `{code}` → `{analysis_id}`；`GET /api/analysis/{id}`；`GET /api/analysis?list=1`
- `GET /sse/analysis/{id}`：SSE 事件 `agent`（每个 Agent 输出）、`decision`、完成时 `done`。前端 EventSource。
- `GET/POST /api/plans` `PUT/DELETE /api/plans/{id}` `POST /api/plans/from-analysis/{analysis_id}`（decision→计划字段映射）
- `GET/POST /api/triggers` `PUT/DELETE /api/triggers/{id}`
- `GET /api/paper/account` `GET /api/paper/positions` `POST /api/paper/order` `{code, side, quantity, price?}` `GET /api/paper/orders`
- `GET/POST /api/journal` `PUT/DELETE /api/journal/{id}`
- `GET /api/templates?agent=` `PUT /api/templates/{id}` `GET /api/templates/{id}/versions`
- `GET /api/reports/{analysis_id}/markdown`（text/markdown）
- 未登录接口仅 auth；其余全部 JWT Bearer。

## 5. 13 Agent 编排（agents/graph.py，串行 Pipeline 即可，不引入 LangGraph 依赖）
依次：fundamentals / market / news / social_media 4 分析师 → bull vs bear 轮流辩论 2 轮 → research_manager 综合 → trader 出计划 → conservative/neutral/aggressive 3 辩手评估 → risk_manager 终审 → 汇总 decision+report。
每步：取该 agent 的活跃模板（无则内置默认模板）→ 调 LLMClient.mock_llm（mock 模式生成确定性中文内容）→ 写入 analysis_events 并推 SSE。
Agent 模板选择优先级：该父 ter 请求参数指定的 variant > 用户设置 > is_active 默认。

## 6. 前端页面与路由（views/）
`/login` `/dashboard` `/screening` `/favorites` `/analysis`（单股+批量+历史列表）`/analysis/:id`（辩论时间线 Timeline，SSE 实时追加 + decision 卡片 + Markdown 报告）`/plans` `/triggers` `/paper`（账户/持仓/下单/订单）`/journal` `/templates` `/settings`。
布局：Element Plus 左侧菜单 Admin 布局 (`components/Layout.vue`)。`api/client.ts` 封装 axios（拦截器加 token、错误 toast）。
全局页脚/页眉常显：`本系统仅用于学习研究，不构成投资建议`。

## 7. 编码约定
- 后端：中文变量注释、均带 try/except 返回统一错误；SQLite 线程问题用 `check_same_thread=False` + `scoped_session`。
- 前端：全部 `<script setup lang="ts">`，组合式；ECharts 仅用于 paper 权益曲线与 journal 统计。
- 所有金额/价格保留 2 位小数；时间戳 ISO8601。
- 每个文件顶部注释一行：`# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议`（前端用 `//`）。
- requirements 全部固定次版本号（允许 `~=`）。

## 8. 验收标准（v3.0 MVP）
1. `docker compose up --build` 一条命令起来，访问 80 端口可注册登录。
2. 无 LLM key 时 mock 分析全程走通：列表可见 13 类 agent 输出按序到达、最终有 decision 与 Markdown 报告。
3. 计划→触发器（价格触发 mock 轮询）→ 自动下模拟单 → 复盘写 journal，全链路可用。
4. Ubuntu 裸机脚本一键安装（python venv + npm build + systemd 可选）。

## 9. 分工与文件归属（严格按归属写文件，禁止跨目录改别人文件）
见任务书各子代理 prompt；冲突文件（如 schemas）由指定代理单独维护。

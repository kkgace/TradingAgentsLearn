# TradingAgents-Calv v3.0 子代理任务书

> 通用规则（每节都适用）：
> 1. 项目根：`D:\work\TradingAgents-Calv`
> 2. 先读契约 `spec\SHARED_SPEC.md`，后端任务还须读 `backend\app\models.py`、`backend\app\core\database.py`、`backend\app\services\llm.py`、`backend\app\services\sse_bus.py`
> 3. 只准创建/修改本节 GivenFiles 列出的文件，禁止动他人文件
> 4. 后端文件顶部写 `# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议`；前端用 `//` 或 `<!-- -->`
> 5. 后端返回统一用 `app.core.security.ok/fail`；前端 API 统一前缀 `/api` 且按 `{code,data,msg}` 解包
> 6. 所有涉及资金/结论的 UI 与报告必须显式标注「本系统仅用于学习研究，不构成投资建议」
> 7. 交付时运行语法自检（后端 `python -m compileall`，前端自查 import），最后回复：完成的文件清单 + 150 字内说明

## T01 auth-router
GivenFiles: `backend/app/routers/auth.py`
任务：用户注册（校验重复）、登录（校验密码签发 JWT，`ok({token, user:{id,username,role}})`）、`GET /auth/me` 返回当前用户。路由前缀 `/auth`。

## T02 stocks-datasource
GivenFiles: `backend/app/services/datasources/__init__.py`, `backend/app/services/datasources/base.py`, `backend/app/services/datasources/mock_source.py`, `backend/app/services/datasources/manager.py`, `backend/app/routers/stocks.py`
任务：base 定义 DataSourceBase(list_stocks, get_quote(code), search(q, market))；mock_source 内置 20 只确定性示例股票（CN/HK/US 混合，含 600519 贵州茅台、000001 平安银行、00700 腾讯、AAPL 苹果 等，pe/pb/price 合理）；manager.get_source() 默认 mock；stocks.py 提供 `GET /stocks/search`、`GET /stocks/{code}/quote`、`GET /stocks/list` 并把 mock 数据 upsert 进 Stock 表。

## T03 screening
GivenFiles: `backend/app/routers/screening.py`
任务：`POST /screening/run` 接收 `{min_pe?,max_pe?,min_pb?,max_pb?,markets?:[],limit?=50}`，查 Stock 表返回命中列表（字段含 code/name/market/industry/pe/pb/price）。

## T04 favorites
GivenFiles: `backend/app/routers/favorites.py`
任务：自选股 `GET /favorites`、`POST /favorites {code, group_name?}`（重复则幂等）、`DELETE /favorites/{id}`、`GET /favorites/groups`。归属当前用户。

## T05 analysis-core（最关键）
GivenFiles: `backend/app/agents/__init__.py`, `backend/app/agents/default_templates.py`, `backend/app/agents/prompt_loader.py`, `backend/app/agents/graph.py`, `backend/app/services/analysis_runner.py`, `backend/app/routers/analysis.py`
任务：
- default_templates.py：定义 13 个 agent 的中文 system 模板字典（fundamentals/market/news/social_media/bull/bear/research_manager/trader/conservative_debator/neutral_debator/aggressive_debator/risk_manager/final_summary），每个含 default 与 conservative 两变体；
- prompt_loader.py：`load_prompt(db, agent_name, variant="default")` 查 PromptTemplate 表兜底内置模板；
- graph.py：`run_pipeline(db, analysis_id, code, variant)` 串行依次执行 13 步；每步调 `llm_client.chat(system, user)`（user 中拼接股票基础信息与上游摘要），然后插入 AnalysisEvent(seq 递增, agent_name, kind, content) 并 `bus.publish(f"analysis:{analysis_id}", {"type":"agent","seq":..,"agent":..,"kind":..,"content":..})`；最终步生成 decision JSON（action/target_price/confidence/risk_score/summary）发布 `{"type":"decision",...}` 与 `{"type":"done"}`；
- analysis_runner.py：后台 `threading.Thread` 执行 run_pipeline，更新 Analysis.status/report_md/decision/finished_at，异常时 status=failed + error；
- analysis.py：`POST /analysis/start {code}` → 创建 Analysis 并起线程，返回 `{analysis_id}`；`GET /analysis/{id}` 返回分析+事件列表；`GET /analysis` 当前用户历史列表。注意 SQLite：线程内新建 SessionLocal 并关闭。

## T06 plans
GivenFiles: `backend/app/routers/plans.py`
任务：计划 CRUD + `POST /plans/from-analysis/{analysis_id}`：读取该分析 decision JSON，映射 direction=action、target_price、entry_price=target*0.97、stop_price=target*0.93、risk_pct=0.01，生成 Plan(status=draft)。归属当前用户。

## T07 triggers
GivenFiles: `backend/app/routers/triggers.py`
任务：触发器 CRUD（type: price_above/price_below，params JSON {"price": x}）；创建时校验 plan 属于当前用户且 plan.status=draft/active；DELETE 逻辑关闭。

## T08 paper-engine（模拟盘）
GivenFiles: `backend/app/services/paper_engine.py`, `backend/app/routers/paper.py`
任务：
- engine：`place_order(db, user_id, code, side, qty, price=None, plan_id=None)`；按 code 前缀识别市场（6 位数字=CN、5 位=HK、字母=US）；价格缺省取 Stock.price；佣金 CN=万3最低5，HK=万3+卖出印花税0.13%，US=0；买入扣对应币种现金，卖出结算并累计 realized_pnl_cny（外汇按固定汇率 HKD→CNY 0.92、USD→CNY 7.2 折算）；维护 PaperPosition(qty, avg_cost)；提供 `get_account(db,user_id)`（没有则创建默认账户）；
- paper.py：`GET /paper/account`、`GET /paper/positions`、`POST /paper/order {code,side,qty,price?}`、`GET /paper/orders`。

## T09 journal
GivenFiles: `backend/app/routers/journal.py`
任务：复盘 CRUD + `GET /journal/stats`：近 30 天成交订单统计胜率（卖出且 pnl>0 比例）、平均单笔 PnL、按计划执行率（有 plan_id 的订单占比）。

## T10 templates-bootstrap
GivenFiles: `backend/app/routers/templates.py`, `backend/app/worker/__init__.py`, `backend/app/worker/bootstrap.py`
任务：templates.py —— `GET /templates?agent=`、`PUT /templates/{id}`（编辑后 version+1 并存档策略：保留旧行为即可，版本字段自增）、`GET /templates/{id}/versions`（当前版本信息）；bootstrap.py —— `ensure_default_templates()`：遍历 13 个 agent × (default, conservative)，若 PromptTemplate 无记录则从 app.agents.default_templates 导入写入；在模块导入时自动执行（main 启动 init_db 之后被触发，放在 templates.py 的 startup 不可行，直接在 bootstrap 提供并在 main 已有逻辑之外无需改动——仅提供函数并在 app.main 现有时机不适用，函数内自行建 Session）。

## T11 fe-shell（前端基座，其他前端都依赖）
GivenFiles: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/router/index.ts`, `frontend/src/stores/auth.ts`, `frontend/src/stores/app.ts`, `frontend/src/api/client.ts`, `frontend/src/api/index.ts`
任务：Vue3+TS+Vite5+Element Plus+Pinia+Vue Router+ECharts 依赖齐全（锁定稳定版本号）；vite proxy `/api`/`/sse` → `http://localhost:8000`；client.ts axios 实例带 Bearer token 拦截器与错误 toast；api/index.ts 导出各后端接口函数；router 注册全部页面（Login/Dashboard/Screening/Favorites/Analysis/AnalysisDetail/Plans/Triggers/Paper/Journal/Templates/Settings），未登录跳 /login；auth store 管 token(localStorage)。

## T12 fe-layout-login
GivenFiles: `frontend/src/components/Layout.vue`, `frontend/src/views/Login.vue`, `frontend/src/views/Dashboard.vue`
任务：Layout 用 Element Plus 侧边栏菜单（对应全部路由）+ 顶栏用户菜单 + 页脚合规声明；Login 登录/注册二合一；Dashboard 快捷入口卡片（发起分析/模拟盘/我的计划/复盘）+ 提示卡片。

## T13 fe-analysis（SSE 可视化核心）
GivenFiles: `frontend/src/views/Analysis.vue`, `frontend/src/views/AnalysisDetail.vue`
任务：Analysis.vue 输入股票代码发起分析 + 批量发起（代码逗号分隔）+ 历史列表跳转详情；AnalysisDetail.vue 用 EventSource(`${location.origin}/sse/analysis/${id}?...`，注意 token 需要可带——采用 fetch EventSource 替代方案：原生 EventSource 不支持 header，用 URL query 传 token）按时间线渲染 agent 事件（Element Plus Timeline，kind 着色），完成后显示 decision 卡片（action/目标价/置信度/风险分，带色块）+ Markdown 报告（用 marked 渲染，自己 npm 加依赖并在此处 import）+「生成交易计划」按钮调 `/api/plans/from-analysis/:id`。

## T14 fe-workflow
GivenFiles: `frontend/src/views/Screening.vue`, `frontend/src/views/Favorites.vue`, `frontend/src/views/Plans.vue`, `frontend/src/views/Triggers.vue`
任务：Screening(pe/pb 范围输入+市场多选+结果表格+「加入自选/发起分析」按钮)；Favorites(分组管理+列表+删除)；Plans(状态标签+表格+编辑对话框)；Triggers(表格+新建对话框选计划/类型/价格+开关)。

## T15 fe-paper-journal
GivenFiles: `frontend/src/views/Paper.vue`, `frontend/src/views/Journal.vue`, `frontend/src/views/Templates.vue`, `frontend/src/views/Settings.vue`
任务：Paper(账户三币种卡片+下单对话框+持仓表格+订单历史)；Journal(日记列表+编辑器+近30天统计卡片)；Templates(13 agent 分组展示+template 编辑抽屉+版本号展示)；Settings(LLM 模式显示 mock/live、数据源说明、合规声明、关于)。

## T16 deliver（交付）
GivenFiles: `backend/app/worker/scheduler.py`, `backend/app/routers/reports.py`, `backend/Dockerfile`, `frontend/Dockerfile`, `nginx/nginx.conf`, `docker-compose.yml`, `scripts/deploy_ubuntu.sh`, `README.md`
任务：scheduler.py —— APScheduler 后台任务：每 TRIGGER_POLL_SECONDS 扫描 Trigger(status=on, type=price_above/below)，用 Stock.price 命中后置 fired/fired_at 并调用 paper_engine.place_order 为 plan 执行一笔模拟单（买入用 plan.entry_price），同时 `bus.publish("triggers", {...})`；注意独立 SessionLocal、异常吞噬；提供 `start_scheduler()`。reports.py —— `GET /reports/{analysis_id}/markdown` 返回 PlainTextResponse。Dockerfile 后端 python:3.11-slim + requirements + uvicorn；前端 node:20 build + nginx:alpine 二阶段；nginx.conf SPA fallback + /api、/sse 反代 backend:8000（SSE 加 proxy_buffering off）；docker-compose 两个服务；deploy_ubuntu.sh —— apt 装 python3.11-venv/nodejs/git，python -m venv + pip install -r requirements.txt，npm ci + npm run build，用 nohup/任选方式启动 uvicorn 与静态服务说明，附 systemd unit 模板（注释形式）；README.md 完整中文文档（简介/架构图 ascii/快速开始 docker 与裸机/环境变量/合规声明）。

## T17 docs
GivenFiles: `docs/ARCHITECTURE.md`, `docs/AGENT_PIPELINE.md`, `docs/QUICKSTART.md`
任务：ARCHITECTURE（模块与数据流 ascii 图、扩展点）；AGENT_PIPELINE（13 agent 顺序与职责表、模板生效优先级、SSE 事件格式 type=agent/decision/done 的 JSON 结构示例）；QUICKSTART（docker compose up --build 与 Ubuntu 裸机两种、默认账户说明、mock 模式说明）。

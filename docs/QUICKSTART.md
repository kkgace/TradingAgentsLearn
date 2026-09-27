<!-- TradingAgents-Calv v3.0 | 教育用途，不构成投资建议 -->
# 快速上手（QUICKSTART）

> 本系统仅用于学习研究，不构成投资建议。模拟盘为虚拟资金。

## 方式一：Docker Compose（推荐）

前置：已安装 Docker 与 Docker Compose 插件。

```bash
git clone <repo> && cd TradingAgents-Calv
docker compose up --build
```

启动后访问 **http://localhost**（nginx 80 端口，自动反代 `/api` 与 `/sse` 到后端 backend:8000）。

## 方式二：Ubuntu 裸机

前置：Ubuntu 20.04+，已安装 git。

```bash
git clone <repo> && cd TradingAgents-Calv
bash scripts/deploy_ubuntu.sh
```

脚本会：安装 python3.11-venv / nodejs → 创建 venv 并 `pip install -r backend/requirements.txt` → 前端 `npm ci && npm run build` → 以 nohup 启动 uvicorn（脚本内附 systemd unit 模板，可按需启用）。

手动方式等价于：

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

cd ../frontend && npm ci && npm run build
# 用任意静态服务器托管 frontend/dist，并把 /api、/sse 反代到 127.0.0.1:8000
```

开发模式（前端热更新）：

```bash
cd frontend && npm run dev   # Vite 已配置 /api、/sse 代理到 localhost:8000
```

## 默认账户

系统不预置账号，首次打开页面在 **登录页可直接注册**（登录/注册二合一表单）。注册即登录，获得 JWT 后可使用全部功能。

## Mock 模式说明

- **LLM Mock**：未配置 `LLM_API_KEY` 时自动进入 Mock 模式，13 个 Agent 输出为确定性中文教学示例，SSE 全程照常推送，离线可完整演示「筛选 → 分析 → 计划 → 触发 → 模拟盘 → 复盘」闭环。接入真实模型：设置环境变量 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`（OpenAI 兼容协议）。
- **行情 Mock**：默认数据源为内置 MockDataSource（20 只确定性示例股票，含 600519/000001/00700/AAPL 等）。配置 `TUSHARE_TOKEN` 后自动切换为 Tushare 数据源（A 股日线；未覆盖代码与调用失败自动回退 Mock）。**中转站地址、token 与股票池也可在「设置」页在线修改**（保存即生效，优先级高于 .env）。

## 常用环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI 兼容模型接入 | 空（Mock 模式） |
| `TUSHARE_TOKEN` / `TUSHARE_CODES` | Tushare Pro 接口令牌与股票池（逗号分隔 6 位代码） | 空（Mock 数据源）/ 内置 10 只 A 股 |
| `TUSHARE_API` | Tushare 接口地址，可改为自建中转站（兼容 Tushare Pro HTTP 协议） | `http://api.tushare.pro` |
| `ENABLE_SCHEDULER` | 是否启动触发器轮询调度器 | true |
| `TRIGGER_POLL_SECONDS` | 触发器轮询间隔（秒） | 30 |
| `SECRET_KEY` | JWT 签名密钥 | 生产环境务必修改 |

## 验证清单

1. 打开首页 → 注册/登录 ✅
2. 「发起分析」输入 `600519` → 详情页可见 13 类 Agent 事件按序到达，最终出现 decision 卡片与 Markdown 报告 ✅
3. 从分析生成交易计划 → 建触发器（价格触发）→ 命中后模拟盘自动产生订单 → 复盘页写 journal ✅

## 合规声明

本系统仅用于学习研究，不构成投资建议。所有分析结论由 AI 生成，仅供教学演示。

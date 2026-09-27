#!/usr/bin/env bash
# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
# Ubuntu 裸机一键部署脚本（测试基线：Ubuntu 22.04/24.04）
# 用法：bash scripts/deploy_ubuntu.sh
set -euo pipefail

# 仓库根目录（scripts/ 的上一级）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "===== [1/5] 安装系统依赖（python3.11-venv / nodejs / git / build-essential） ====="
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip git curl build-essential

# Node.js 20（若系统没有 nodejs，使用 NodeSource 安装）
if ! command -v node >/dev/null 2>&1; then
  echo "===== 安装 Node.js 20 ====="
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "===== [2/5] 后端：创建 venv 并安装依赖 ====="
cd "$ROOT/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "===== [3/5] 前端：安装依赖并构建静态产物 ====="
cd "$ROOT/frontend"
npm ci
npm run build

echo "===== [4/5] 生成运行环境变量（backend/.env，已存在则跳过） ====="
cd "$ROOT/backend"
if [ ! -f .env ]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > .env <<EOF
# 修改为你的真实密钥/模型；不配置 LLM_* 则全系统自动进入 MOCK 演示模式
JWT_SECRET=$SECRET
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
# Tushare 数据源（https://tushare.pro 注册获取）；不配置则使用 Mock 数据源
# 也可使用自定义中转站：TUSHARE_API 填中转站地址（需兼容 Tushare Pro HTTP 协议）
# 界面（设置页）亦可在线修改，优先级高于本文件
TUSHARE_TOKEN=
TUSHARE_API=
TUSHARE_CODES=600519,000001,300750,601318,600036,002594,000858,601899,600276,000651
ENABLE_SCHEDULER=true
TRIGGER_POLL_SECONDS=30
EOF
  echo "已生成 backend/.env（含随机 JWT_SECRET），请按需修改。"
fi

echo "===== [5/5] 启动服务 ====="
# 后端：后台运行 uvicorn（日志在 backend/uvicorn.log）
cd "$ROOT/backend"
nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
echo "后端已启动: http://localhost:8000/api/health"

# 前端：任选其一
#  A) 简单演示：用 python 静态服务托管 dist（SPA fallback 不完整，仅演示）
#     nohup python3 -m http.server 8080 -d "$ROOT/frontend/dist" > frontend.log 2>&1 &
#  B) 生产建议：安装 nginx，将 frontend/dist 设 root，
#     反代 /api /sse 到 http://127.0.0.1:8000（可直接参考仓库 nginx/nginx.conf 的 location 段，
#     把 proxy_pass 的 backend:8000 改成 127.0.0.1:8000）。
echo "前端静态产物位于 $ROOT/frontend/dist，请用 nginx 等托管并反代 /api、/sse 到 127.0.0.1:8000"

: <<'SYSTEMD_EOF'
# ========== systemd unit 模板（可选，取消注释并按需安装到 /etc/systemd/system/calv-backend.service） ==========
# [Unit]
# Description=TradingAgents-Calv v3.0 Backend
# After=network.target
#
# [Service]
# Type=simple
# WorkingDirectory=/opt/TradingAgents-Calv/backend
# ExecStart=/opt/TradingAgents-Calv/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# Restart=always
# RestartSec=5
#
# [Install]
# WantedBy=multi-user.target
# ==========================================================================================================
SYSTEMD_EOF

echo "部署完成。本系统仅用于学习研究，不构成投资建议。"

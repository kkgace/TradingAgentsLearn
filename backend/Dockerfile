# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
FROM python:3.11-slim

WORKDIR /app

# 后端依赖（全部固定次版本号，见 requirements.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码（SQLite 数据文件默认落在 /app/data/calv.db，可挂卷持久化）
COPY app ./app
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

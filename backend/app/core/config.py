# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

class Settings(BaseSettings):
    APP_NAME: str = "TradingAgents-Calv v3.0"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'calv.db'}"
    JWT_SECRET: str = "calv-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7
    # LLM（OpenAI 兼容协议；不配置则全系统走 MOCK）
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    # Tushare 数据源（https://tushare.pro；不配置 token 则全局走 Mock 数据源）
    TUSHARE_TOKEN: str = ""
    TUSHARE_API: str = "http://api.tushare.pro"
    TUSHARE_CODES: str = ("600519,000001,300750,601318,600036,"
                          "002594,000858,601899,600276,000651")   # 股票池（6 位代码）
    TUSHARE_TIMEOUT: int = 10
    # 调度器
    ENABLE_SCHEDULER: bool = True
    TRIGGER_POLL_SECONDS: int = 30

    class Config:
        env_file = ".env"

settings = Settings()

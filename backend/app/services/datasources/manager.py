# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""数据源管理器：按「界面配置(AppSetting 表) > .env 环境变量 > 内置默认」解析配置。

- 有效 token 存在时使用 Tushare 数据源（A 股日线，支持自定义中转站地址）
- 未配置 token 或初始化失败时自动降级 Mock 数据源
- 界面修改配置后调用 reset_source() 立即生效（无需重启）
"""
import json
import logging

from .base import DataSourceBase
from .mock_source import MockDataSource

logger = logging.getLogger(__name__)

_source: DataSourceBase | None = None


def resolve_datasource_config() -> dict:
    """解析生效的数据源配置 {token, api, codes}（AppSetting 覆盖 > env）。

    必须用独立短连接读 AppSetting，绝不能用 SessionLocal()：scoped_session 按
    线程复用同一 Session，close() 会把调用方正持有的 ORM 对象全部 expunge
    （DetachedInstanceError）——调度器轮询线程与请求线程都会踩中。
    """
    from app.core.config import settings
    cfg = {
        "token": settings.TUSHARE_TOKEN or "",
        "api": settings.TUSHARE_API or "http://api.tushare.pro",
        "codes": [c.strip() for c in (settings.TUSHARE_CODES or "").split(",") if c.strip()],
    }
    try:
        from sqlalchemy import select

        from app.core.database import engine
        from app.models import AppSetting
        from app.services.app_settings import DATASOURCE_KEY
        with engine.connect() as conn:
            raw = conn.execute(select(AppSetting.value)
                               .where(AppSetting.key == DATASOURCE_KEY)).scalar()
        if raw:
            override = json.loads(raw)
            if isinstance(override, dict):
                if override.get("tushare_api"):
                    cfg["api"] = str(override["tushare_api"]).strip()
                if override.get("tushare_token"):
                    cfg["token"] = str(override["tushare_token"]).strip()
                if override.get("tushare_codes"):
                    codes = [str(c).strip() for c in override["tushare_codes"]
                             if str(c).strip()]
                    if codes:
                        cfg["codes"] = codes
    except Exception as e:
        logger.warning("读取界面数据源配置失败，按 .env/默认继续：%s", e)
    return cfg


def get_source() -> DataSourceBase:
    """返回当前数据源（按需初始化；Tushare 初始化失败自动降级 Mock）"""
    global _source
    if _source is not None:
        return _source
    cfg = resolve_datasource_config()
    if cfg["token"]:
        try:
            from .tushare_source import TushareSource
            _source = TushareSource(token=cfg["token"], api=cfg["api"],
                                    universe=cfg["codes"])
            logger.info("数据源：Tushare（api=%s，股票池 %d 只）", cfg["api"], len(cfg["codes"]))
        except Exception as e:
            logger.warning("Tushare 数据源初始化失败，降级 Mock：%s", e)
            _source = MockDataSource()
    else:
        _source = MockDataSource()
        logger.info("数据源：Mock（未配置 TUSHARE_TOKEN）")
    return _source


def reset_source() -> None:
    """清除数据源单例：下次 get_source() 按最新配置重建（界面保存后调用）"""
    global _source
    _source = None


def current_source_name() -> str:
    """当前生效数据源名（mock / tushare）；未初始化时先初始化"""
    return get_source().name

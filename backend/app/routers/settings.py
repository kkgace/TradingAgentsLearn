# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""系统设置路由：数据源（Tushare/中转站）界面配置。

- GET    /api/settings/datasource       查看生效配置（token 脱敏）
- PUT    /api/settings/datasource       保存覆盖项并即时生效（无需重启；空值=回退 .env）
- POST   /api/settings/datasource/test  用候选配置试连（trade_cal 最便宜的接口）
- DELETE /api/settings/datasource       清除全部界面覆盖，回退 .env/内置默认
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, ok, fail
from app.services.app_settings import DATASOURCE_KEY, clear_setting, get_setting, set_setting
from app.services.datasources import manager
from app.services.datasources.tushare_source import TushareAPIError, TushareSource, to_ts_code

router = APIRouter(prefix="/settings", tags=["settings"])


class DatasourceUpdate(BaseModel):
    tushare_api: Optional[str] = None       # 中转站地址；空=回退 .env
    tushare_token: Optional[str] = None     # token；空=回退 .env
    tushare_codes: Optional[list[str]] = None  # 股票池；空列表=回退 .env


class DatasourceTest(BaseModel):
    tushare_api: Optional[str] = None       # 不填则用当前生效地址
    tushare_token: Optional[str] = None     # 不填则用当前生效 token


def _mask(token: str) -> str | None:
    """token 脱敏展示：只露头尾各 4 位"""
    if not token:
        return None
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}****{token[-4:]}"


def _payload(db: Session) -> dict:
    cfg = manager.resolve_datasource_config()
    override = get_setting(db, DATASOURCE_KEY) or {}
    return {
        "tushare_api": cfg["api"],
        "tushare_token_masked": _mask(cfg["token"]),
        "token_configured": bool(cfg["token"]),
        "tushare_codes": ",".join(cfg["codes"]),
        "overridden_keys": sorted(k for k in override if override.get(k)),
        "active_source": manager.current_source_name(),
        "default_api": "http://api.tushare.pro",
        "note": "界面配置优先于 .env；删除覆盖项即回退 .env。行情为 A 股日线数据，仅用于学习研究。",
    }


@router.get("/datasource")
def get_datasource(db: Session = Depends(get_db), _=Depends(get_current_user)):
    try:
        return ok(_payload(db))
    except Exception as e:
        return fail(f"读取数据源配置失败：{e}")


@router.put("/datasource")
def update_datasource(body: DatasourceUpdate, db: Session = Depends(get_db),
                      _=Depends(get_current_user)):
    """按提交字段做增量覆盖；字段留空即清除该项覆盖（回退 .env）。保存后立即生效。"""
    try:
        data = body.model_dump(exclude_unset=True)
        override = get_setting(db, DATASOURCE_KEY) or {}

        if "tushare_api" in data:
            api = (data["tushare_api"] or "").strip()
            if api and not (api.startswith("http://") or api.startswith("https://")):
                return fail("中转站地址必须以 http:// 或 https:// 开头")
            if api:
                override["tushare_api"] = api
            else:
                override.pop("tushare_api", None)

        if "tushare_token" in data:
            token = (data["tushare_token"] or "").strip()
            if token:
                override["tushare_token"] = token
            else:
                override.pop("tushare_token", None)

        if "tushare_codes" in data:
            codes = [str(c).strip() for c in (data["tushare_codes"] or []) if str(c).strip()]
            if codes:
                bad = [c for c in codes if not to_ts_code(c)]
                if bad:
                    return fail(f"股票池含非 A 股代码（需 6 位数字）：{', '.join(bad)}")
                override["tushare_codes"] = codes
            else:
                override.pop("tushare_codes", None)

        if override:
            set_setting(db, DATASOURCE_KEY, override)
        else:
            clear_setting(db, DATASOURCE_KEY)
        manager.reset_source()                    # 立即生效（下次取数据即用新配置）
        return ok(_payload(db), msg="数据源配置已保存并生效。本系统仅用于学习研究，不构成投资建议")
    except Exception as e:
        db.rollback()
        return fail(f"保存数据源配置失败：{e}")


@router.delete("/datasource")
def reset_datasource(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """清除全部界面覆盖，回退 .env/内置默认"""
    try:
        removed = clear_setting(db, DATASOURCE_KEY)
        manager.reset_source()
        return ok(_payload(db),
                  msg="已清除界面覆盖，回退 .env/默认配置" if removed else "本无界面覆盖项")
    except Exception as e:
        db.rollback()
        return fail(f"重置数据源配置失败：{e}")


@router.post("/datasource/test")
def test_datasource(body: DatasourceTest = Body(default=DatasourceTest()),
                    db: Session = Depends(get_db), _=Depends(get_current_user)):
    """试连候选配置（不落库）：请求字段 > 界面覆盖 > .env"""
    try:
        base = manager.resolve_datasource_config()
        api = (body.tushare_api or "").strip() or base["api"]
        token = body.tushare_token if body.tushare_token is not None else base["token"]
        if not token:
            return ok({"ok": False, "api": api, "msg": "未配置 token，无法测试"})
        src = TushareSource(token=token, api=api)
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        try:
            rows = src._request("trade_cal", {"exchange": "SSE", "start_date": start,
                                              "end_date": end}, "cal_date,is_open")
            return ok({"ok": True, "api": api,
                       "msg": f"连接成功：{api} 返回 {len(rows)} 条交易日历记录"})
        except TushareAPIError as e:
            return ok({"ok": False, "api": api, "msg": f"连接失败：{e}"})
    except Exception as e:
        return fail(f"测试连接失败：{e}")

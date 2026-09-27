# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""数据源界面配置测试：AppSetting 存取、DB>.env 优先级、API 保存/脱敏/即时生效/试连"""
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_token
from app.main import app
from app.services.app_settings import (DATASOURCE_KEY, clear_setting, get_setting,
                                      set_setting)
from app.services.datasources import manager
from app.services.datasources.tushare_source import TushareSource


@pytest.fixture
def client(user):
    TestClient(app)                      # 触发 app 生命周期（startup）
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {create_token(user.id, user.username)}"})
    yield c
    manager.reset_source()              # 防止污染其他用例


@pytest.fixture(autouse=True)
def _clean_override(db):
    clear_setting(db, DATASOURCE_KEY)
    manager.reset_source()
    yield
    clear_setting(db, DATASOURCE_KEY)
    manager.reset_source()


# ---------- AppSetting 存取 ----------

def test_app_setting_set_get_clear(db):
    assert get_setting(db, DATASOURCE_KEY) is None
    set_setting(db, DATASOURCE_KEY, {"tushare_api": "https://relay.example.com"})
    assert get_setting(db, DATASOURCE_KEY)["tushare_api"] == "https://relay.example.com"
    assert clear_setting(db, DATASOURCE_KEY) is True
    assert get_setting(db, DATASOURCE_KEY) is None
    assert clear_setting(db, DATASOURCE_KEY) is False       # 再删为 False


# ---------- 配置解析优先级：界面(DB) > .env > 内置默认 ----------

def test_resolve_config_defaults(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "")
    cfg = manager.resolve_datasource_config()
    assert cfg["token"] == ""
    assert cfg["api"] == "http://api.tushare.pro"
    assert cfg["codes"][:2] == ["600519", "000001"]


def test_resolve_config_db_overrides_env(db, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "env-token")
    set_setting(db, DATASOURCE_KEY, {
        "tushare_api": "https://relay.example.com",
        "tushare_token": "ui-token",
        "tushare_codes": ["600519"],
    })
    cfg = manager.resolve_datasource_config()
    assert cfg["token"] == "ui-token"                       # DB 覆盖 env
    assert cfg["api"] == "https://relay.example.com"
    assert cfg["codes"] == ["600519"]
    clear_setting(db, DATASOURCE_KEY)
    cfg = manager.resolve_datasource_config()
    assert cfg["token"] == "env-token"                     # 清除后回退 env


# ---------- API：查看 / 保存 / 恢复 ----------

def test_api_get_masks_token(client):
    r = client.get("/api/settings/datasource")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["active_source"] == "mock"                  # 测试环境无 token
    assert data["token_configured"] is False
    assert data["tushare_api"] == "http://api.tushare.pro"


def test_api_put_saves_and_applies_immediately(client, db):
    r = client.put("/api/settings/datasource", json={
        "tushare_api": "https://relay.example.com",
        "tushare_token": "sk-ui-token-1234567890",
        "tushare_codes": ["600519", "000001"],
    })
    assert r.json()["code"] == 0
    data = r.json()["data"]
    assert data["tushare_api"] == "https://relay.example.com"
    assert data["token_configured"] is True
    assert data["tushare_token_masked"].startswith("sk-u")
    assert data["tushare_token_masked"].endswith("7890")
    assert "sk-ui-token" not in data["tushare_token_masked"][4:-4]
    assert data["active_source"] == "tushare"              # 保存后立即切换数据源
    src = manager.get_source()
    assert isinstance(src, TushareSource)
    assert src._api == "https://relay.example.com"
    assert src._universe == ["600519", "000001"]


def test_api_put_rejects_bad_values(client):
    r = client.put("/api/settings/datasource", json={"tushare_api": "relay.example.com"})
    assert r.json()["code"] != 0                           # 缺 http(s)://
    r = client.put("/api/settings/datasource", json={"tushare_codes": ["00700"]})
    assert r.json()["code"] != 0                           # 非 6 位 A 股代码


def test_api_delete_reverts_to_env(client, db):
    client.put("/api/settings/datasource", json={"tushare_token": "sk-ui-token"})
    r = client.delete("/api/settings/datasource")
    assert r.json()["code"] == 0
    assert r.json()["data"]["active_source"] == "mock"      # 测试环境 env 无 token
    assert get_setting(db, DATASOURCE_KEY) is None


def test_api_requires_auth():
    c = TestClient(app)
    assert c.get("/api/settings/datasource").status_code == 401


# ---------- 试连：请求字段 > 界面覆盖 > .env ----------

def test_api_test_ok(client, monkeypatch):
    seen = {}

    def fake_request(self, api_name, params, fields):
        seen["api_name"] = api_name
        seen["api"] = self._api
        seen["token"] = self._token
        return [{"cal_date": "20260924", "is_open": "1"}]

    monkeypatch.setattr(TushareSource, "_request", fake_request)
    r = client.post("/api/settings/datasource/test",
                    json={"tushare_api": "https://relay.example.com",
                          "tushare_token": "candidate-token"})
    data = r.json()["data"]
    assert data["ok"] is True
    assert seen["api_name"] == "trade_cal"
    assert seen["api"] == "https://relay.example.com"
    assert seen["token"] == "candidate-token"


def test_api_test_failure_returns_ok_false(client, monkeypatch):
    def fake_request(self, api_name, params, fields):
        from app.services.datasources.tushare_source import TushareAPIError
        raise TushareAPIError("积分不足或地址无法访问")

    monkeypatch.setattr(TushareSource, "_request", fake_request)
    r = client.post("/api/settings/datasource/test", json={"tushare_token": "t"})
    data = r.json()["data"]
    assert data["ok"] is False and "连接失败" in data["msg"]


def test_api_test_without_token(client):
    r = client.post("/api/settings/datasource/test", json={})
    data = r.json()["data"]
    assert data["ok"] is False and "token" in data["msg"]

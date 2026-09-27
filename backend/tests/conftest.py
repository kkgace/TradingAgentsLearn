# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""测试公共配置：必须在导入任何 app 模块前设置环境变量。

- DATABASE_URL 指向临时目录的 SQLite，避免污染开发库 backend/data/calv.db
- LLM 密钥留空 -> 全局 MOCK 模式，测试确定性
- ENABLE_SCHEDULER=false -> 不启动后台轮询
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="calv_test_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/calv_test.db")
os.environ.setdefault("LLM_BASE_URL", "")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
# 硬性覆盖宿主机环境变量：测试必须封闭在 MOCK 数据源下运行，
# 否则开发机配置了真实 TUSHARE_TOKEN 时用例会打到真实接口
os.environ["TUSHARE_TOKEN"] = ""

import pytest  # noqa: E402

from app import models  # noqa: E402,F401  注册全部模型
from app.core.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    """会话级建表（临时库）"""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """每个用例独立 Session；结束后清空全部业务表，保证用例隔离"""
    session = SessionLocal()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def user(db):
    """内置测试用户"""
    u = models.User(username="tester", password_hash="x", role="user")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

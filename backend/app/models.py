# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime

# 统一使用本地时间的 Python 侧默认值。此前 default=datetime.now 在 SQLite 上
# 生成 UTC 时间，与代码里 datetime.now() 混用会造成同一记录前后时间相差 8 小时。
from .core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, index=True, nullable=False)
    name = Column(String(64))
    market = Column(String(4), default="CN")
    industry = Column(String(64))
    currency = Column(String(8), default="CNY")
    pe = Column(Float)
    pb = Column(Float)
    price = Column(Float)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    group_name = Column(String(64), default="默认")
    code = Column(String(16), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    code = Column(String(16), index=True, nullable=False)
    status = Column(String(16), default="pending")       # pending|running|done|failed
    params = Column(Text)                                 # JSON
    decision = Column(Text)                               # JSON
    report_md = Column(Text)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)

class AnalysisEvent(Base):
    __tablename__ = "analysis_events"
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, index=True, nullable=False)
    seq = Column(Integer, nullable=False)
    agent_name = Column(String(64), nullable=False)
    kind = Column(String(16), nullable=False)  # analyst|researcher|debator|manager|trader|decision
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id = Column(Integer, primary_key=True)
    agent_name = Column(String(64), index=True, nullable=False)
    variant = Column(String(32), default="default")
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    analysis_id = Column(Integer)
    code = Column(String(16), nullable=False)
    direction = Column(String(8), default="buy")  # buy|hold|reduce|sell
    entry_price = Column(Float)
    stop_price = Column(Float)
    target_price = Column(Float)
    risk_pct = Column(Float, default=0.01)
    note = Column(Text)
    status = Column(String(16), default="draft")  # draft|active|done|cancelled
    created_at = Column(DateTime, default=datetime.now)

class Trigger(Base):
    __tablename__ = "triggers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    plan_id = Column(Integer, nullable=False)
    type = Column(String(32), default="price_above")  # price_above|price_below
    params = Column(Text)  # JSON {"price": 12.34}
    status = Column(String(8), default="on")          # on|off|fired
    fired_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    cash_cny = Column(Float, default=1000000.0)
    cash_hkd = Column(Float, default=0.0)
    cash_usd = Column(Float, default=0.0)
    realized_pnl_cny = Column(Float, default=0.0)

class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    plan_id = Column(Integer)
    code = Column(String(16), nullable=False)
    market = Column(String(4), default="CN")
    side = Column(String(4), nullable=False)  # buy|sell
    qty = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(8), default="CNY")
    commission = Column(Float, default=0.0)
    status = Column(String(16), default="filled")  # filled|rejected
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class PaperPosition(Base):
    __tablename__ = "paper_positions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    code = Column(String(16), nullable=False)
    market = Column(String(4), default="CN")
    qty = Column(Integer, default=0)
    avg_cost = Column(Float, default=0.0)
    currency = Column(String(8), default="CNY")

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    plan_id = Column(Integer)
    title = Column(String(128), nullable=False)
    content = Column(Text)
    pnl = Column(Float)
    adherence_score = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

class AppSetting(Base):
    """运行时应用设置（key-value，value 存 JSON 字符串）。
    界面保存的数据源等配置写在这里，优先级高于 .env；删除记录即回退 .env。"""
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

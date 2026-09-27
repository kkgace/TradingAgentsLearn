# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""模拟盘引擎：多币种账户、撮合成交、持仓维护、已实现盈亏折算 CNY。

市场识别规则：6 位数字=CN(A股)，5 位数字=HK(港股)，其余按字母代码视为 US(美股)。
佣金规则：CN=万3 最低 5 元；HK=万3，卖出另收印花税 0.13%；US=0。
汇率（固定折算）：HKD→CNY 0.92，USD→CNY 7.2，CNY=1.0。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PaperAccount, PaperOrder, PaperPosition, Stock

# 固定折算汇率（学习用途，非实时汇率）
FX_TO_CNY = {"CNY": 1.0, "HKD": 0.92, "USD": 7.2}

# 市场 -> 币种
MARKET_CURRENCY = {"CN": "CNY", "HK": "HKD", "US": "USD"}


def detect_market(code: str) -> str:
    """按 code 前缀识别市场：6 位数字=CN、5 位=HK、字母=US"""
    code = (code or "").strip().upper()
    if code.isdigit():
        if len(code) == 6:
            return "CN"
        if len(code) == 5:
            return "HK"
    return "US"


def _commission(market: str, side: str, amount: float) -> float:
    """按市场计算佣金（金额 2 位小数）"""
    if amount <= 0:
        return 0.0
    if market == "CN":
        return round(max(amount * 0.0003, 5.0), 2)          # 万3 最低 5 元
    if market == "HK":
        fee = amount * 0.0003                                # 万3
        if side == "sell":
            fee += amount * 0.0013                           # 印花税 0.13%（仅卖出）
        return round(fee, 2)
    return 0.0                                               # US 免佣


def get_account(db: Session, user_id: int) -> PaperAccount:
    """获取用户模拟账户，不存在则创建默认账户（100 万 CNY）"""
    acc = db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
    if not acc:
        acc = PaperAccount(user_id=user_id, cash_cny=1000000.0,
                           cash_hkd=0.0, cash_usd=0.0, realized_pnl_cny=0.0)
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def _acct_field(currency: str) -> str:
    return {"CNY": "cash_cny", "HKD": "cash_hkd", "USD": "cash_usd"}[currency]


def place_order(db: Session, user_id: int, code: str, side: str,
                qty: int, price: Optional[float] = None,
                plan_id: Optional[int] = None) -> PaperOrder:
    """撮合一笔模拟单（同步、即时成交）。失败返回 status=rejected 的订单记录。

    注意：本函数可能抛出 ValueError（参数非法）；调用方据此返回 fail。
    """
    code = (code or "").strip().upper()
    side = (side or "").strip().lower()
    if not code:
        raise ValueError("股票代码不能为空")
    if side not in ("buy", "sell"):
        raise ValueError("side 必须为 buy/sell")
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        raise ValueError("数量必须为整数")
    if qty <= 0:
        raise ValueError("数量必须为正整数")

    market = detect_market(code)
    currency = MARKET_CURRENCY[market]

    # 价格缺省取 Stock 表最新价
    stock = db.query(Stock).filter(Stock.code == code).first()
    if price is None:
        if stock and stock.price:
            price = float(stock.price)
        else:
            raise ValueError(f"无法取得 {code} 价格，请显式传入 price")
    price = round(float(price), 2)
    if price <= 0:
        raise ValueError("价格必须为正数")

    acc = get_account(db, user_id)
    amount = round(price * qty, 2)
    commission = _commission(market, side, amount)

    order = PaperOrder(user_id=user_id, plan_id=plan_id, code=code, market=market,
                       side=side, qty=qty, price=price, currency=currency,
                       commission=commission, status="filled")

    cash_attr = _acct_field(currency)
    cash = float(getattr(acc, cash_attr) or 0.0)

    # 持仓记录（user_id+code 唯一）
    pos = db.query(PaperPosition).filter(PaperPosition.user_id == user_id,
                                         PaperPosition.code == code).first()

    if side == "buy":
        cost = round(amount + commission, 2)
        if cash < cost:
            order.status = "rejected"
            order.reason = f"{currency} 现金不足：需 {cost:.2f}，现有 {cash:.2f}"
            db.add(order)
            db.commit()
            db.refresh(order)
            return order
        setattr(acc, cash_attr, round(cash - cost, 2))
        # 持仓加权成本
        if pos:
            new_qty = int(pos.qty) + qty
            new_cost = (float(pos.avg_cost) * int(pos.qty) + amount + commission) / new_qty
            pos.qty = new_qty
            pos.avg_cost = round(new_cost, 2)
        else:
            pos = PaperPosition(user_id=user_id, code=code, market=market,
                                qty=qty, avg_cost=round((amount + commission) / qty, 2),
                                currency=currency)
            db.add(pos)
    else:  # sell
        if not pos or int(pos.qty) < qty:
            have = int(pos.qty) if pos else 0
            order.status = "rejected"
            order.reason = f"持仓不足：需卖出 {qty}，现有 {have}"
            db.add(order)
            db.commit()
            db.refresh(order)
            return order
        proceeds = round(amount - commission, 2)
        setattr(acc, cash_attr, round(cash + proceeds, 2))
        # 已实现盈亏（按持仓均价折算 CNY 累计）
        pnl_native = (price - float(pos.avg_cost)) * qty - commission
        acc.realized_pnl_cny = round(float(acc.realized_pnl_cny or 0.0)
                                     + pnl_native * FX_TO_CNY.get(currency, 1.0), 2)
        pos.qty = int(pos.qty) - qty
        if pos.qty == 0:
            db.delete(pos)

    db.add(order)
    db.commit()
    db.refresh(order)
    return order

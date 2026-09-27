# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""端到端冒烟脚本（非 pytest 用例）：对运行中的服务走完整闭环。

前置：服务已用临时库启动，例如
  DATABASE_URL=sqlite:///.../calv_smoke.db TRIGGER_POLL_SECONDS=5 \
  ENABLE_SCHEDULER=true uvicorn app.main:app --port 8123

链路：注册/登录 -> 行情(验证漂移) -> 13-Agent 分析 -> 决策 -> 计划 -> 触发器
      -> 后台轮询自动下单 -> 模拟盘账户/持仓校验
用法：python tests/smoke_e2e.py [base_url]
"""
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123").rstrip("/")
API = BASE + "/api"
CODE = "000001"          # 平安银行：锚定价 11.35，2 万预算可买整数手

_failed = False


def check(name: str, cond: bool, detail: str = ""):
    global _failed
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))
    if not cond:
        _failed = True


def wait_server(client: httpx.Client, tries: int = 30):
    for _ in range(tries):
        try:
            if client.get(API + "/health", timeout=2).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("服务未在 30s 内就绪")


def get_retry(c: httpx.Client, url: str, headers: dict, tries: int = 3):
    """带传输层重试的 GET：休眠跨越 uvicorn keep-alive(5s) 空闲超时会掐断连接"""
    for i in range(tries):
        try:
            return c.get(url, headers=headers)
        except httpx.TransportError:
            if i == tries - 1:
                raise
            time.sleep(0.5)


def main():
    with httpx.Client(timeout=15) as c:
        wait_server(c)

        # ---- 认证 ----
        uname = f"smoke_{int(time.time())}"
        r = c.post(API + "/auth/register", json={"username": uname, "password": "pass1234"})
        check("注册", r.json()["code"] == 0, r.text[:80])
        r = c.post(API + "/auth/login", json={"username": uname, "password": "pass1234"})
        token = r.json()["data"]["token"]
        H = {"Authorization": f"Bearer {token}"}
        check("登录", bool(token))

        # ---- SSE 无 token 应 401 ----
        r = c.get(BASE + "/sse/analysis/1")
        check("SSE 未带 token 拒绝", r.status_code == 401)

        # ---- 数据源配置：GET 脱敏 / 试连 / PUT+DELETE 回环 ----
        r = c.get(API + "/settings/datasource", headers=H)
        ds = r.json()["data"]
        check("数据源配置读取", r.json()["code"] == 0 and ds["active_source"] in ("mock", "tushare"),
              f"active={ds['active_source']} token_configured={ds['token_configured']}")
        if ds.get("tushare_token_masked"):
            check("token 脱敏", "*" in ds["tushare_token_masked"] and len(ds["tushare_token_masked"]) < 20)
        r = c.post(API + "/settings/datasource/test", json={}, headers=H)
        tr = r.json()["data"]
        check("试连接口返回结果", "ok" in tr and "msg" in tr, f"ok={tr['ok']} {tr['msg'][:40]}")
        r = c.put(API + "/settings/datasource", json={"tushare_api": "https://smoke-relay.invalid"},
                  headers=H)
        check("保存覆盖项", r.json()["code"] == 0 and
              r.json()["data"]["tushare_api"] == "https://smoke-relay.invalid")
        r = c.delete(API + "/settings/datasource", headers=H)
        check("恢复默认回环", r.json()["code"] == 0 and
              r.json()["data"]["tushare_api"] != "https://smoke-relay.invalid")

        # ---- 行情：拿到漂移价 ----
        r = c.get(API + f"/stocks/search?q={CODE}", headers=H)
        rows = r.json()["data"]
        check("股票检索", len(rows) == 1 and rows[0]["code"] == CODE, f"price={rows[0]['price']}")
        first_price = rows[0]["price"]

        # ---- 观察漂移：行情应跨档变化（观察性检查，波动性已由单测保证，软告警）----
        changed = None
        for _ in range(25):
            time.sleep(3)
            p = get_retry(c, API + f"/stocks/search?q={CODE}", H).json()["data"][0]["price"]
            if p != first_price:
                changed = p
                break
        if changed is not None:
            check("行情漂移(<=75s)", True, f"{first_price} -> {changed}")
        else:
            print(f"[WARN] 行情漂移 —— {first_price} 在观察窗内未变化"
                  f"（处于平台期；确定性波动已由单元测试覆盖）")

        # ---- 分析：13 Agent + 决策 ----
        r = c.post(API + "/analysis/start", json={"code": CODE}, headers=H)
        aid = r.json()["data"]["analysis_id"]
        check("发起分析", aid > 0, f"analysis_id={aid}")

        detail = {}
        for _ in range(30):
            time.sleep(1)
            detail = c.get(API + f"/analysis/{aid}", headers=H).json()["data"]
            if detail["status"] in ("done", "failed"):
                break
        check("分析完成", detail.get("status") == "done",
              f"status={detail.get('status')} err={detail.get('error')}")
        events = detail.get("events") or []
        check("事件数=14", len(events) == 14, f"实际 {len(events)}")
        check("决策为 hold(MOCK 确定性)", detail["decision"]["action"] == "hold",
              f"decision={detail['decision']}")
        check("决策摘要非空", bool(detail["decision"].get("summary")))
        check("报告含最终决策", "最终决策" in (detail.get("report_md") or ""))

        # ---- 计划（decision -> 字段映射）----
        r = c.post(API + f"/plans/from-analysis/{aid}", headers=H)
        plan = r.json()["data"]
        check("生成计划", plan["id"] > 0 and plan["status"] == "draft",
              f"direction={plan['direction']} entry={plan['entry_price']}")

        # ---- 触发器（price_above 1 元必命中）----
        r = c.post(API + "/triggers", headers=H,
                   json={"plan_id": plan["id"], "type": "price_above", "params": {"price": 1.0}})
        trig = r.json()["data"]
        check("创建触发器", r.json()["code"] == 0 and trig["status"] == "on",
              f"trigger_id={trig['id']}")

        # ---- 等后台轮询命中 -> 自动下单 -> 计划闭环 ----
        fired = None
        for _ in range(24):                    # TRIGGER_POLL_SECONDS=5 -> 最多 ~2 分钟
            time.sleep(5)
            trig = get_retry(c, API + f"/triggers", H).json()["data"][0]
            if trig["status"] == "fired":
                fired = trig
                break
        check("触发器命中", fired is not None,
              f"fired_at={fired['fired_at'] if fired else '未命中'}")
        check("计划闭环置 done", fired and fired["plan_status"] == "done")

        orders = get_retry(c, API + "/paper/orders", H).json()["data"]
        filled = [o for o in orders if o["status"] == "filled"]
        check("自动下单成交", len(filled) == 1,
              f"order={ {k: filled[0][k] for k in ('side','qty','price','commission')} if filled else '无' }")
        if filled:
            o = filled[0]
            check("订单归属计划", o.get("plan_id") == plan["id"])
            expect_qty = int(20000 // (plan["entry_price"] * 100)) * 100
            check("数量按预算取整手", o["qty"] == expect_qty, f"qty={o['qty']} 期望={expect_qty}")

            account = get_retry(c, API + "/paper/account", H).json()["data"]
            positions = get_retry(c, API + "/paper/positions", H).json()["data"]
            check("现金扣减", account["cash_cny"] < 1000000.0, f"cash={account['cash_cny']}")
            check("持仓生成", len(positions) == 1 and positions[0]["qty"] == o["qty"],
                  f"avg_cost={positions[0]['avg_cost'] if positions else '无'}")

    print("\n冒烟结果：", "全部通过 ✅" if not _failed else "存在失败项 ❌")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()

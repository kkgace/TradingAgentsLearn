# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from fastapi import Depends

from app.core.database import init_db, get_db
from app.core.security import get_current_user
from app.services.sse_bus import bus

from app.routers import auth, stocks, screening, favorites, analysis, plans, triggers, paper, journal, templates, reports, settings as settings_router

def create_app() -> FastAPI:
    app = FastAPI(title="TradingAgents-Calv v3.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    init_db()
    try:
        from app.worker.bootstrap import ensure_default_templates
        ensure_default_templates()
    except Exception as e:
        print(f"[bootstrap] 跳过默认模板回填: {e}")

    for r in (auth.router, stocks.router, screening.router, favorites.router,
              analysis.router, plans.router, triggers.router, paper.router,
              journal.router, templates.router, reports.router, settings_router.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"code": 0, "data": {"status": "ok", "version": "3.0.0"}, "msg": "ok"}

    @app.get("/sse/analysis/{analysis_id}")
    async def sse_analysis(analysis_id: int, token: str = ""):
        # EventSource 无法带 Header，故用 query token 鉴权
        if not token:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="missing token")
        from jose import jwt, JWTError
        from app.core.config import settings
        try:
            jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except JWTError:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="invalid token")
        # 总线按订阅者各自的事件循环投递，无需（也不允许）全局绑定循环
        return EventSourceResponse(bus.subscribe(f"analysis:{analysis_id}"))

    # 后台调度器（触发器轮询；跑在自身线程，通过 SSE 总线跨线程发布事件）
    from app.core.config import settings
    if settings.ENABLE_SCHEDULER:
        def _start_sched():
            try:
                from app.worker.scheduler import start_scheduler
                start_scheduler()
            except Exception:
                pass
        threading.Thread(target=_start_sched, daemon=True).start()

    return app

app = create_app()

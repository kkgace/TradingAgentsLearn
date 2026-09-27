# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""后台线程执行分析流水线：独立 Session，状态落库，异常置 failed"""
import json
import threading
from datetime import datetime

from app.core.database import SessionLocal
from app.models import Analysis


def _run(analysis_id: int, code: str, variant: str):
    from app.agents.graph import run_pipeline  # 延迟导入避免循环依赖
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        analysis.status = "running"
        db.commit()

        result = run_pipeline(db, analysis_id, code, variant)

        analysis.status = "done"
        analysis.decision = json.dumps(result["decision"], ensure_ascii=False)
        analysis.report_md = result["report_md"]
        analysis.finished_at = datetime.now()
        db.commit()
    except Exception as e:  # 任何异常都落库，不外抛
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.error = str(e)[:500]
                analysis.finished_at = datetime.now()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def start_analysis(analysis_id: int, code: str, variant: str = "default"):
    """启动后台分析线程（daemon）"""
    t = threading.Thread(target=_run, args=(analysis_id, code, variant),
                         daemon=True, name=f"analysis-{analysis_id}")
    t.start()
    return t

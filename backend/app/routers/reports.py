# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""报告路由：GET /reports/{analysis_id}/markdown 返回纯文本 Markdown 报告"""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Analysis, User

router = APIRouter(prefix="/reports", tags=["reports"])

DISCLAIMER = "\n\n---\n> 本系统仅用于学习研究，不构成投资建议。\n"


@router.get("/{analysis_id}/markdown", response_class=PlainTextResponse)
def get_report_markdown(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """返回指定分析的 Markdown 报告（text/markdown），仅本人可见，尾部附合规声明"""
    ana = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user.id)
        .first()
    )
    if not ana:
        return PlainTextResponse("报告不存在或不属于当前用户。\n" + DISCLAIMER,
                                 status_code=404, media_type="text/markdown; charset=utf-8")
    content = ana.report_md or "（该分析尚未生成报告内容）"
    return PlainTextResponse(content + DISCLAIMER,
                             media_type="text/markdown; charset=utf-8")

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.models import ProviderCallLog, User
from app.db.session import get_db
from app.main_templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/provider-call-logs")
def provider_call_logs(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    logs = db.scalars(
        select(ProviderCallLog).order_by(ProviderCallLog.created_at.desc()).limit(100)
    ).all()
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request,
            "provider_logs.html",
            {"logs": logs},
        )
    return [
        {
            "id": log.id,
            "provider": log.provider,
            "operation": log.operation,
            "model": log.model,
            "prompt_tokens": log.prompt_tokens,
            "completion_tokens": log.completion_tokens,
            "total_tokens": log.total_tokens,
            "estimated_cost_usd": str(log.estimated_cost_usd),
            "status": log.status,
            "latency_ms": log.latency_ms,
            "error_message": log.error_message,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/provider-call-logs/ui", response_class=HTMLResponse)
def provider_call_logs_page(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    logs = db.scalars(
        select(ProviderCallLog).order_by(ProviderCallLog.created_at.desc()).limit(100)
    ).all()
    return templates.TemplateResponse(request, "provider_logs.html", {"logs": logs})

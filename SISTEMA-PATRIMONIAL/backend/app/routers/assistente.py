"""
Router do Assistente IA — chat com Claude via SSE streaming.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Tenant
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.config_service import TenantConfigService
from app.services.llm_service import chat_stream

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def assistente_page(
    request: Request,
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    return templates.TemplateResponse(
        "assistente/chat.html",
        {"request": request, "usuario": usuario, "tenant": tenant},
    )


@router.post("/chat")
async def chat(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    body = await request.json()
    mensagens = body.get("mensagens", [])

    svc = TenantConfigService(tenant)
    api_key = svc.get_llm_api_key()  # None se não configurado → fallback em llm_service

    return StreamingResponse(
        chat_stream(mensagens, db, tenant.id, api_key=api_key),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

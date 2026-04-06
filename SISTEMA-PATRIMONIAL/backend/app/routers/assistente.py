"""
Router do Assistente IA — chat com Claude via SSE streaming.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Tenant
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.config_service import TenantConfigService
from app.services.llm_service import chat_stream

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/status")
def assistente_status(
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """Retorna se o tenant tem chave Claude configurada. Usado pelo indicador na sidebar."""
    svc = TenantConfigService(tenant)
    return JSONResponse({"conectado": svc.has_llm_api_key()})


@router.get("/", response_class=HTMLResponse)
def assistente_page(
    request: Request,
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    svc = TenantConfigService(tenant)
    return templates.TemplateResponse(
        "assistente/chat.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "ia_conectada": svc.has_llm_api_key(),
        },
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

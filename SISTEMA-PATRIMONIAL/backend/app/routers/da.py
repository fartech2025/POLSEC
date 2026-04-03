from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Tenant
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.da_service import gerar_insights

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def da_page(
    request: Request,
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    return templates.TemplateResponse(
        "da/painel.html",
        {"request": request, "usuario": usuario, "tenant": tenant},
    )


@router.post("/analisar")
def analisar(
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    try:
        resultado = gerar_insights(db, tenant.id)
        return JSONResponse(content=resultado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

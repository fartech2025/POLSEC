from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.movimentacao import Movimentacao
from app.models.tenant import Tenant
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def listar(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    historico = (
        db.query(Movimentacao)
        .filter(Movimentacao.tenant_id == tenant.id)
        .order_by(Movimentacao.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        "movimentacao/lista.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "historico": historico,
        },
    )

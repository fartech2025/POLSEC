from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.tenant import Tenant
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    total = (
        db.query(func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant.id)
        .scalar()
    )
    por_status = (
        db.query(Patrimonio.status, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant.id)
        .group_by(Patrimonio.status)
        .all()
    )
    por_setor = (
        db.query(Patrimonio.setor, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant.id)
        .group_by(Patrimonio.setor)
        .order_by(func.count(Patrimonio.id).desc())
        .limit(10)
        .all()
    )

    status_map = {s.value: 0 for s in StatusPatrimonio}
    for s, count in por_status:
        status_map[s.value] = count

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "total": total,
            "status_map": status_map,
            "por_setor": por_setor,
        },
    )

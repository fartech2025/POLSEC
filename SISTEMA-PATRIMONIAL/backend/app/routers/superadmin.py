"""
SuperAdmin Router — exclusivo para o perfil FARTECH (superadmin).
Visão global da plataforma: tenants, usuários, saúde do sistema.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.tenant import Tenant
from app.models.usuario import Usuario, PerfilUsuario
from app.services.auth_service import get_usuario_logado

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _exigir_superadmin(usuario: Usuario = Depends(get_usuario_logado)) -> Usuario:
    if usuario.perfil != PerfilUsuario.superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à equipe FARTECH.",
        )
    return usuario


@router.get("/", response_class=HTMLResponse)
def superadmin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_superadmin),
):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    total_tenants = len(tenants)
    tenants_ativos = sum(1 for t in tenants if t.ativo)

    total_usuarios = db.query(func.count(Usuario.id)).scalar()
    usuarios_ativos = db.query(func.count(Usuario.id)).filter(Usuario.ativo == True).scalar()

    # Usuários por tenant (para tabela)
    usuarios_por_tenant = (
        db.query(Usuario.tenant_id, func.count(Usuario.id))
        .group_by(Usuario.tenant_id)
        .all()
    )
    usuarios_map = {tid: cnt for tid, cnt in usuarios_por_tenant}

    # Planos
    planos = (
        db.query(Tenant.plano, func.count(Tenant.id))
        .group_by(Tenant.plano)
        .all()
    )

    return templates.TemplateResponse(
        "superadmin/dashboard.html",
        {
            "request": request,
            "usuario": usuario,
            "tenants": tenants,
            "total_tenants": total_tenants,
            "tenants_ativos": tenants_ativos,
            "total_usuarios": total_usuarios,
            "usuarios_ativos": usuarios_ativos,
            "usuarios_map": usuarios_map,
            "planos": planos,
        },
    )


@router.get("/tenants", response_class=HTMLResponse)
def superadmin_tenants(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_superadmin),
):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    usuarios_por_tenant = dict(
        db.query(Usuario.tenant_id, func.count(Usuario.id))
        .group_by(Usuario.tenant_id)
        .all()
    )
    return templates.TemplateResponse(
        "superadmin/tenants.html",
        {
            "request": request,
            "usuario": usuario,
            "tenants": tenants,
            "usuarios_map": usuarios_por_tenant,
        },
    )


@router.post("/tenants/{tenant_id}/toggle", response_class=HTMLResponse)
def toggle_tenant(
    tenant_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_superadmin),
):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    t.ativo = not t.ativo
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/superadmin/tenants", status_code=303)

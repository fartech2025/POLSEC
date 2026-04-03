"""
Router Admin — vistas exclusivas do perfil administrador.
Gestão operacional: chamados, funcionários, usuários, cargos, filiais.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models.chamado import Chamado, StatusChamado, PrioridadeChamado
from app.models.funcionario import Funcionario
from app.models.usuario import PerfilUsuario, Usuario
from app.models.tenant import Tenant
from app.models.cargo import Cargo
from app.models.filial import Filial
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Guard ─────────────────────────────────────────────────────────────────────

def _exigir_admin(usuario: Usuario = Depends(get_usuario_logado)) -> Usuario:
    if usuario.perfil not in (PerfilUsuario.administrador, PerfilUsuario.superadmin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario


# ── Painel principal admin ─────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request):
    return RedirectResponse(url="/admin/chamados", status_code=302)


# ── Painel de chamados ─────────────────────────────────────────────────────────

@router.get("/chamados", response_class=HTMLResponse)
def admin_chamados(
    request: Request,
    status_filtro: str = "",
    prioridade: str = "",
    tecnico_id: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    q = (
        db.query(Chamado)
        .options(
            joinedload(Chamado.patrimonio),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.tecnico),
        )
        .filter(Chamado.tenant_id == tenant.id)
    )
    if status_filtro:
        q = q.filter(Chamado.status == status_filtro)
    if prioridade:
        q = q.filter(Chamado.prioridade == prioridade)
    if tecnico_id:
        q = q.filter(Chamado.tecnico_id == int(tecnico_id))

    chamados = q.order_by(Chamado.data_abertura.desc()).all()

    # Técnicos disponíveis para atribuição
    tecnicos = (
        db.query(Funcionario)
        .filter(Funcionario.tenant_id == tenant.id, Funcionario.ativo == True)
        .order_by(Funcionario.nome)
        .all()
    )

    # KPIs
    def _c(st): return sum(1 for c in chamados if c.status == st)
    stats = {
        "total": len(chamados),
        "abertos": _c(StatusChamado.aberto),
        "em_atendimento": _c(StatusChamado.em_atendimento),
        "aguardando": _c(StatusChamado.aguardando_peca) + _c(StatusChamado.aguardando_aprovacao),
        "concluidos": _c(StatusChamado.concluido),
    }

    return templates.TemplateResponse(
        "admin/chamados.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "chamados": chamados,
            "tecnicos": tecnicos,
            "stats": stats,
            "status_filtro": status_filtro,
            "prioridade": prioridade,
            "tecnico_id": tecnico_id,
            "StatusChamado": StatusChamado,
        },
    )


@router.post("/chamados/{chamado_id}/atribuir")
def atribuir_tecnico(
    chamado_id: int,
    tecnico_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    chamado = (
        db.query(Chamado)
        .filter(Chamado.id == chamado_id, Chamado.tenant_id == tenant.id)
        .first()
    )
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    # Verifica que o técnico pertence ao tenant
    tec = db.query(Funcionario).filter(
        Funcionario.id == tecnico_id, Funcionario.tenant_id == tenant.id
    ).first()
    if not tec:
        raise HTTPException(status_code=400, detail="Técnico inválido.")
    chamado.tecnico_id = tecnico_id
    db.commit()
    return RedirectResponse(url="/admin/chamados", status_code=303)


@router.post("/chamados/{chamado_id}/fechar")
def fechar_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    chamado = (
        db.query(Chamado)
        .filter(Chamado.id == chamado_id, Chamado.tenant_id == tenant.id)
        .first()
    )
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    chamado.status = StatusChamado.cancelado
    db.commit()
    return RedirectResponse(url="/admin/chamados", status_code=303)


# ── Funcionários ───────────────────────────────────────────────────────────────

@router.get("/funcionarios", response_class=HTMLResponse)
def admin_funcionarios(
    request: Request,
    busca: str = "",
    cargo_id: str = "",
    filial_id: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    q = (
        db.query(Funcionario)
        .options(joinedload(Funcionario.cargo), joinedload(Funcionario.filial))
        .filter(Funcionario.tenant_id == tenant.id)
    )
    if busca:
        q = q.filter(
            Funcionario.nome.ilike(f"%{busca}%") | Funcionario.matricula.ilike(f"%{busca}%")
        )
    if cargo_id:
        q = q.filter(Funcionario.cargo_id == int(cargo_id))
    if filial_id:
        q = q.filter(Funcionario.filial_id == int(filial_id))

    funcionarios = q.order_by(Funcionario.nome).all()
    cargos = db.query(Cargo).filter(Cargo.tenant_id == tenant.id).order_by(Cargo.nome).all()
    filiais = db.query(Filial).filter(Filial.tenant_id == tenant.id).order_by(Filial.nome).all()

    return templates.TemplateResponse(
        "admin/funcionarios.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "funcionarios": funcionarios,
            "cargos": cargos,
            "filiais": filiais,
            "busca": busca,
            "cargo_id": cargo_id,
            "filial_id": filial_id,
        },
    )


@router.post("/funcionarios/{func_id}/toggle")
def toggle_funcionario(
    func_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    f = db.query(Funcionario).filter(
        Funcionario.id == func_id, Funcionario.tenant_id == tenant.id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    f.ativo = not f.ativo
    db.commit()
    return RedirectResponse(url="/admin/funcionarios", status_code=303)


# ── Usuários ───────────────────────────────────────────────────────────────────

@router.get("/usuarios", response_class=HTMLResponse)
def admin_usuarios(
    request: Request,
    busca: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    q = db.query(Usuario).filter(Usuario.tenant_id == tenant.id)
    if busca:
        q = q.filter(
            Usuario.nome.ilike(f"%{busca}%") | Usuario.email.ilike(f"%{busca}%")
        )
    usuarios = q.order_by(Usuario.nome).all()

    return templates.TemplateResponse(
        "admin/usuarios.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "usuarios": usuarios,
            "busca": busca,
            "PerfilUsuario": PerfilUsuario,
        },
    )


@router.post("/usuarios/{uid}/toggle")
def toggle_usuario(
    uid: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    u = db.query(Usuario).filter(
        Usuario.id == uid, Usuario.tenant_id == tenant.id
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    # Não desativar a si mesmo
    if u.id == usuario.id:
        raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta.")
    u.ativo = not u.ativo
    db.commit()
    return RedirectResponse(url="/admin/usuarios", status_code=303)


@router.post("/usuarios/{uid}/perfil")
def alterar_perfil(
    uid: int,
    novo_perfil: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    u = db.query(Usuario).filter(
        Usuario.id == uid, Usuario.tenant_id == tenant.id
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if u.id == usuario.id:
        raise HTTPException(status_code=400, detail="Você não pode alterar seu próprio perfil.")
    # Administrador não pode promover a superadmin
    try:
        perfil = PerfilUsuario(novo_perfil)
    except ValueError:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
    if perfil == PerfilUsuario.superadmin:
        raise HTTPException(status_code=403, detail="Apenas a FARTECH pode atribuir superadmin.")
    u.perfil = perfil
    db.commit()
    return RedirectResponse(url="/admin/usuarios", status_code=303)

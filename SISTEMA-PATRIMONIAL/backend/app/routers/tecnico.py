"""
Painel do Técnico — exclusivo para o perfil operador.
Mostra chamados atribuídos, permite atualizar diagnóstico, solução e status.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.chamado import Chamado, PrioridadeChamado, StatusChamado
from app.models.funcionario import Funcionario
from app.models.patrimonio import Patrimonio
from app.models.usuario import PerfilUsuario, Usuario
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.models.tenant import Tenant

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Guard ─────────────────────────────────────────────────────────────────────

def _exigir_operador(usuario: Usuario = Depends(get_usuario_logado)) -> Usuario:
    # superadmin pode navegar por qualquer interface para suporte/debug
    if usuario.perfil == PerfilUsuario.visualizador:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Visualizadores não têm acesso ao painel de técnicos.",
        )
    return usuario


def _get_funcionario(usuario: Usuario, tenant: Tenant, db: Session) -> Funcionario | None:
    """Retorna o Funcionario vinculado ao Usuario logado, se houver."""
    return (
        db.query(Funcionario)
        .filter(
            Funcionario.usuario_id == usuario.id,
            Funcionario.tenant_id == tenant.id,
        )
        .first()
    )


# ── Painel principal ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def painel_tecnico(
    request: Request,
    prioridade: str = "",
    status_filtro: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_operador),
    tenant: Tenant = Depends(get_tenant_atual),
):
    # superadmin não tem painel técnico — redireciona ao seu próprio dashboard
    if usuario.perfil == PerfilUsuario.superadmin:
        return RedirectResponse(url="/superadmin", status_code=302)
    funcionario = _get_funcionario(usuario, tenant, db)

    q = (
        db.query(Chamado)
        .options(
            joinedload(Chamado.patrimonio),
            joinedload(Chamado.solicitante),
        )
        .filter(Chamado.tenant_id == tenant.id)
        .filter(Chamado.status != StatusChamado.cancelado)
    )

    if funcionario:
        q = q.filter(Chamado.tecnico_id == funcionario.id)

    if prioridade:
        q = q.filter(Chamado.prioridade == prioridade)
    if status_filtro:
        q = q.filter(Chamado.status == status_filtro)

    chamados = q.order_by(Chamado.data_abertura.desc()).all()

    # KPIs
    def _count(st: StatusChamado) -> int:
        return sum(1 for c in chamados if c.status == st)

    stats = {
        "abertos": _count(StatusChamado.aberto),
        "em_atendimento": _count(StatusChamado.em_atendimento),
        "aguardando_peca": _count(StatusChamado.aguardando_peca),
        "aguardando_aprovacao": _count(StatusChamado.aguardando_aprovacao),
        "concluidos": _count(StatusChamado.concluido),
    }

    return templates.TemplateResponse(
        "tecnico/painel.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "funcionario": funcionario,
            "chamados": chamados,
            "stats": stats,
            "prioridade": prioridade,
            "status_filtro": status_filtro,
            "StatusChamado": StatusChamado,
        },
    )


# ── Novo chamado — formulário ─────────────────────────────────────────────────

@router.get("/chamado/novo", response_class=HTMLResponse)
def form_novo_chamado(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_operador),
    tenant: Tenant = Depends(get_tenant_atual),
):
    if usuario.perfil == PerfilUsuario.superadmin:
        return RedirectResponse(url="/superadmin", status_code=302)

    patrimonios = (
        db.query(Patrimonio)
        .filter(Patrimonio.tenant_id == tenant.id)
        .order_by(Patrimonio.codigo)
        .all()
    )
    funcionarios = (
        db.query(Funcionario)
        .filter(Funcionario.tenant_id == tenant.id, Funcionario.ativo == True)
        .order_by(Funcionario.nome)
        .all()
    )
    funcionario_logado = _get_funcionario(usuario, tenant, db)

    return templates.TemplateResponse(
        "tecnico/novo_chamado.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "patrimonios": patrimonios,
            "funcionarios": funcionarios,
            "funcionario_logado": funcionario_logado,
            "PrioridadeChamado": PrioridadeChamado,
            "erro": None,
        },
    )


@router.post("/chamado/novo", response_class=HTMLResponse)
def criar_chamado(
    request: Request,
    patrimonio_id: int = Form(...),
    titulo: str = Form(...),
    descricao: str = Form(...),
    prioridade: str = Form(...),
    solicitante_id: int = Form(...),
    tecnico_id: int = Form(default=0),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_operador),
    tenant: Tenant = Depends(get_tenant_atual),
):
    if usuario.perfil == PerfilUsuario.superadmin:
        return RedirectResponse(url="/superadmin", status_code=302)

    try:
        prioridade_enum = PrioridadeChamado(prioridade)
    except ValueError:
        prioridade_enum = PrioridadeChamado.media

    chamado = Chamado(
        tenant_id=tenant.id,
        patrimonio_id=patrimonio_id,
        solicitante_id=solicitante_id,
        tecnico_id=tecnico_id if tecnico_id else None,
        titulo=titulo.strip(),
        descricao=descricao.strip(),
        prioridade=prioridade_enum,
        status=StatusChamado.aberto,
        data_abertura=datetime.utcnow(),
    )
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    return RedirectResponse(url=f"/tecnico/chamado/{chamado.id}", status_code=303)


# ── Detalhe do chamado ────────────────────────────────────────────────────────

@router.get("/chamado/{chamado_id}", response_class=HTMLResponse)
def detalhe_chamado(
    chamado_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_operador),
    tenant: Tenant = Depends(get_tenant_atual),
):
    chamado = (
        db.query(Chamado)
        .options(
            joinedload(Chamado.patrimonio),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.tecnico),
        )
        .filter(Chamado.id == chamado_id, Chamado.tenant_id == tenant.id)
        .first()
    )
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")

    funcionario = _get_funcionario(usuario, tenant, db)

    return templates.TemplateResponse(
        "tecnico/chamado.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "chamado": chamado,
            "funcionario": funcionario,
            "StatusChamado": StatusChamado,
        },
    )


# ── Atualizar chamado ─────────────────────────────────────────────────────────

@router.post("/chamado/{chamado_id}/atualizar", response_class=HTMLResponse)
def atualizar_chamado(
    chamado_id: int,
    request: Request,
    novo_status: str = Form(...),
    diagnostico: str = Form(default=""),
    solucao_aplicada: str = Form(default=""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_operador),
    tenant: Tenant = Depends(get_tenant_atual),
):
    chamado = (
        db.query(Chamado)
        .filter(Chamado.id == chamado_id, Chamado.tenant_id == tenant.id)
        .first()
    )
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")

    try:
        st = StatusChamado(novo_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Status inválido.")

    chamado.status = st
    if diagnostico.strip():
        chamado.diagnostico = diagnostico.strip()
    if solucao_aplicada.strip():
        chamado.solucao_aplicada = solucao_aplicada.strip()

    # Preenche datas automáticas
    if st == StatusChamado.em_atendimento and not chamado.data_inicio_atendimento:
        chamado.data_inicio_atendimento = datetime.utcnow()
    elif st == StatusChamado.concluido and not chamado.data_conclusao:
        chamado.data_conclusao = datetime.utcnow()

    db.commit()
    return RedirectResponse(url="/tecnico", status_code=303)

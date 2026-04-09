"""
Router Glosa — gerenciamento do módulo de penalidades contratuais.

Rotas:
  GET  /admin/glosa                — lista de glosas com filtros
  GET  /admin/glosa/novo           — formulário de abertura
  POST /admin/glosa/novo           — processa abertura
  GET  /admin/glosa/{id}           — detalhe de uma glosa
  POST /admin/glosa/{id}/encerrar  — encerra (calcula horas/percentual/valor)
  POST /admin/glosa/{id}/cancelar  — cancela glosa
  GET  /admin/glosa/relatorio      — relatório agregado por filial/período
  GET  /admin/glosa/faixas         — configuração das faixas de percentual
  POST /admin/glosa/faixas/seed    — insere faixas padrão Polsec
"""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status as http_status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.chamado import Chamado, StatusChamado
from app.models.filial import Filial
from app.models.funcionario import Funcionario
from app.models.glosa import GlosaFaixa, GlosaChamado, StatusGlosa
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services import glosa_service
from app.routers._shared import brl as _brl, exigir_admin as _exigir_admin

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["brl"] = _brl


# ── Lista principal ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def glosa_lista(
    request: Request,
    status_filtro: str = "",
    filial_id: str = "",
    ano: str = "",
    mes: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    items, total = glosa_service.listar_glosas(
        tenant_id=tenant.id,
        db=db,
        status=status_filtro or None,
        filial_id=int(filial_id) if filial_id else None,
        ano=int(ano) if ano else None,
        mes=int(mes) if mes else None,
        page=page,
        per_page=30,
    )

    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )

    # KPIs rápidos (todas glosas do tenant, sem filtro de data)
    kpis_q = db.query(
        GlosaChamado.status,
        func.count(GlosaChamado.id).label("qtd"),
        func.sum(GlosaChamado.valor_glosa).label("valor"),
    ).filter(GlosaChamado.tenant_id == tenant.id).group_by(GlosaChamado.status).all()

    kpis = {r.status: {"qtd": r.qtd, "valor": float(r.valor or 0)} for r in kpis_q}

    anos_disponiveis = list(range(2022, datetime.now().year + 1))
    meses = [
        (1, "Jan"), (2, "Fev"), (3, "Mar"), (4, "Abr"),
        (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Ago"),
        (9, "Set"), (10, "Out"), (11, "Nov"), (12, "Dez"),
    ]

    return templates.TemplateResponse(
        "admin/glosa.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "glosas": items,
            "total": total,
            "page": page,
            "per_page": 30,
            "filiais": filiais,
            "kpis": kpis,
            "status_filtro": status_filtro,
            "filial_id_filtro": filial_id,
            "ano_filtro": ano,
            "mes_filtro": mes,
            "anos_disponiveis": anos_disponiveis,
            "meses": meses,
            "StatusGlosa": StatusGlosa,
        },
    )


# ── Nova glosa — formulário ───────────────────────────────────────────────────

@router.get("/novo", response_class=HTMLResponse)
def glosa_novo_form(
    request: Request,
    chamado_id: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )
    chamado_pre = None
    if chamado_id:
        chamado_pre = (
            db.query(Chamado)
            .filter(Chamado.id == int(chamado_id), Chamado.tenant_id == tenant.id)
            .first()
        )
    return templates.TemplateResponse(
        "admin/glosa_form.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "filiais": filiais,
            "chamado_pre": chamado_pre,
            "modo": "novo",
        },
    )


@router.post("/novo")
def glosa_novo_post(
    request: Request,
    filial_id: int = Form(...),
    filial_nome: str = Form(...),
    data_inicio: str = Form(...),
    motivo: str = Form(...),
    chamado_id: str = Form(""),
    valor_base: str = Form(""),
    observacoes: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    try:
        dt_inicio = datetime.fromisoformat(data_inicio)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de início inválida.")

    glosa_service.abrir_glosa(
        tenant_id=tenant.id,
        filial_nome=filial_nome,
        data_inicio=dt_inicio,
        motivo=motivo,
        registrado_por_id=usuario.funcionario_id,
        chamado_id=int(chamado_id) if chamado_id else None,
        filial_id=filial_id or None,
        valor_base=Decimal(valor_base) if valor_base else None,
        observacoes=observacoes or None,
        db=db,
    )
    return RedirectResponse(url="/admin/glosa", status_code=303)


# ── Detalhe ───────────────────────────────────────────────────────────────────

@router.get("/{glosa_id}", response_class=HTMLResponse)
def glosa_detalhe(
    glosa_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    glosa = (
        db.query(GlosaChamado)
        .filter(GlosaChamado.id == glosa_id, GlosaChamado.tenant_id == tenant.id)
        .first()
    )
    if not glosa:
        raise HTTPException(status_code=404, detail="Glosa não encontrada.")

    faixas = (
        db.query(GlosaFaixa)
        .filter(GlosaFaixa.tenant_id == tenant.id, GlosaFaixa.ativo == True)
        .order_by(GlosaFaixa.horas_min)
        .all()
    )

    return templates.TemplateResponse(
        "admin/glosa_detalhe.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "glosa": glosa,
            "faixas": faixas,
            "StatusGlosa": StatusGlosa,
        },
    )


# ── Encerrar ──────────────────────────────────────────────────────────────────

@router.post("/{glosa_id}/encerrar")
def glosa_encerrar(
    glosa_id: int,
    data_fim: str = Form(...),
    observacoes: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    try:
        dt_fim = datetime.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de fim inválida.")

    try:
        glosa_service.encerrar_glosa(
            glosa_id=glosa_id,
            tenant_id=tenant.id,
            data_fim=dt_fim,
            encerrado_por_id=usuario.funcionario_id,
            observacoes=observacoes or None,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(url=f"/admin/glosa/{glosa_id}", status_code=303)


# ── Cancelar ──────────────────────────────────────────────────────────────────

@router.post("/{glosa_id}/cancelar")
def glosa_cancelar(
    glosa_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    glosa = (
        db.query(GlosaChamado)
        .filter(GlosaChamado.id == glosa_id, GlosaChamado.tenant_id == tenant.id)
        .first()
    )
    if not glosa:
        raise HTTPException(status_code=404, detail="Glosa não encontrada.")
    glosa.status = StatusGlosa.cancelada
    glosa.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/admin/glosa", status_code=303)


# ── Relatório ─────────────────────────────────────────────────────────────────

@router.get("/relatorio/periodo", response_class=HTMLResponse)
def glosa_relatorio(
    request: Request,
    ano: str = "",
    mes: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    resumo = glosa_service.resumo_glosa_periodo(
        tenant_id=tenant.id,
        db=db,
        ano=int(ano) if ano else None,
        mes=int(mes) if mes else None,
    )

    # Totais
    total_qtd   = sum(r["qtd"] for r in resumo)
    total_horas = sum(r["horas_total"] for r in resumo)
    total_valor = sum(r["valor_total"] for r in resumo)

    faixas = (
        db.query(GlosaFaixa)
        .filter(GlosaFaixa.tenant_id == tenant.id, GlosaFaixa.ativo == True)
        .order_by(GlosaFaixa.horas_min)
        .all()
    )

    anos_disponiveis = list(range(2022, datetime.now().year + 1))
    meses = [
        (1, "Jan"), (2, "Fev"), (3, "Mar"), (4, "Abr"),
        (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Ago"),
        (9, "Set"), (10, "Out"), (11, "Nov"), (12, "Dez"),
    ]

    return templates.TemplateResponse(
        "admin/glosa_relatorio.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "resumo": resumo,
            "total_qtd": total_qtd,
            "total_horas": total_horas,
            "total_valor": total_valor,
            "faixas": faixas,
            "ano_filtro": ano,
            "mes_filtro": mes,
            "anos_disponiveis": anos_disponiveis,
            "meses": meses,
        },
    )


# ── Faixas de penalidade ──────────────────────────────────────────────────────

@router.get("/faixas/config", response_class=HTMLResponse)
def glosa_faixas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    faixas = (
        db.query(GlosaFaixa)
        .filter(GlosaFaixa.tenant_id == tenant.id)
        .order_by(GlosaFaixa.horas_min)
        .all()
    )
    return templates.TemplateResponse(
        "admin/glosa_faixas.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "faixas": faixas,
        },
    )


@router.post("/faixas/seed")
def glosa_faixas_seed(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """Insere as 5 faixas padrão Polsec (idempotente)."""
    inseridas = glosa_service.seed_faixas_padrao(tenant.id, db)
    return RedirectResponse(
        url=f"/admin/glosa/faixas/config?seed={inseridas}",
        status_code=303,
    )

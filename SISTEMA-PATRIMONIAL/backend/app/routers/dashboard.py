from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date as _date

from app.database import get_db
from app.models.chamado import Chamado, StatusChamado, TipoChamado
from app.models.diesel import GastoDiesel
from app.models.faturamento import FaturamentoHistorico
from app.models.filial import Filial
from app.models.glosa import GlosaChamado
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.tenant import Tenant
from app.models.usuario import PerfilUsuario
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.sla_service import calcular_sla_lote

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_ESTADOS_ATIVOS = [
    StatusChamado.aberto,
    StatusChamado.em_atendimento,
    StatusChamado.aguardando_peca,
    StatusChamado.aguardando_aprovacao,
]


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    if usuario.perfil == PerfilUsuario.superadmin:
        return RedirectResponse(url="/superadmin", status_code=302)
    if usuario.perfil == PerfilUsuario.operador:
        return RedirectResponse(url="/tecnico", status_code=302)

    can_edit = usuario.perfil != PerfilUsuario.visualizador
    _hoje = _date.today()

    # ── Patrimônio ────────────────────────────────────────────────
    total_patrimonios = (
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
    status_map = {s.value: 0 for s in StatusPatrimonio}
    for s, count in por_status:
        status_map[s.value] = count

    # ── Financeiro: Faturamento ───────────────────────────────────
    fat_total_hist = (
        db.query(func.sum(FaturamentoHistorico.valor_total))
        .filter(FaturamentoHistorico.tenant_id == str(tenant.id))
        .scalar() or 0
    )
    ultimo_fat = (
        db.query(
            FaturamentoHistorico.mes,
            FaturamentoHistorico.ano,
            func.sum(FaturamentoHistorico.valor_total).label("total"),
            func.count(FaturamentoHistorico.id).label("unidades"),
        )
        .filter(FaturamentoHistorico.tenant_id == str(tenant.id))
        .group_by(FaturamentoHistorico.mes, FaturamentoHistorico.ano)
        .order_by(FaturamentoHistorico.ano.desc(), FaturamentoHistorico.mes.desc())
        .first()
    )

    # ── Financeiro: Diesel ────────────────────────────────────────
    diesel_valor_mes = (
        db.query(func.coalesce(func.sum(GastoDiesel.valor_total), 0))
        .filter(
            GastoDiesel.tenant_id == tenant.id,
            func.extract("month", GastoDiesel.data) == _hoje.month,
            func.extract("year",  GastoDiesel.data) == _hoje.year,
        )
        .scalar() or 0
    )
    diesel_litros_mes = (
        db.query(func.coalesce(func.sum(GastoDiesel.litros), 0))
        .filter(
            GastoDiesel.tenant_id == tenant.id,
            func.extract("month", GastoDiesel.data) == _hoje.month,
            func.extract("year",  GastoDiesel.data) == _hoje.year,
        )
        .scalar() or 0
    )

    # ── Financeiro: Glosa ─────────────────────────────────────────
    glosa_ativas = (
        db.query(func.count(GlosaChamado.id))
        .filter(GlosaChamado.tenant_id == tenant.id, GlosaChamado.status == "ativa")
        .scalar() or 0
    )
    glosa_valor_mes = (
        db.query(func.coalesce(func.sum(GlosaChamado.valor_glosa), 0))
        .filter(
            GlosaChamado.tenant_id == tenant.id,
            GlosaChamado.status == "encerrada",
            func.extract("year",  GlosaChamado.data_fim) == _hoje.year,
            func.extract("month", GlosaChamado.data_fim) == _hoje.month,
        )
        .scalar() or 0
    )

    # ── Operacional: Chamados ─────────────────────────────────────
    chamados_abertos = (
        db.query(func.count(Chamado.id))
        .filter(Chamado.tenant_id == tenant.id, Chamado.status == StatusChamado.aberto)
        .scalar() or 0
    )
    chamados_em_atendimento = (
        db.query(func.count(Chamado.id))
        .filter(Chamado.tenant_id == tenant.id, Chamado.status == StatusChamado.em_atendimento)
        .scalar() or 0
    )
    chamados_concluidos_mes = (
        db.query(func.count(Chamado.id))
        .filter(
            Chamado.tenant_id == tenant.id,
            Chamado.status == StatusChamado.concluido,
            func.extract("month", Chamado.data_conclusao) == _hoje.month,
            func.extract("year",  Chamado.data_conclusao) == _hoje.year,
        )
        .scalar() or 0
    )
    preventivas_abertas = (
        db.query(func.count(Chamado.id))
        .filter(
            Chamado.tenant_id == tenant.id,
            Chamado.tipo_chamado == TipoChamado.preventiva,
            Chamado.status.in_([StatusChamado.aberto, StatusChamado.em_atendimento]),
        )
        .scalar() or 0
    )
    total_filiais = (
        db.query(func.count(Filial.id))
        .filter(Filial.tenant_id == tenant.id)
        .scalar() or 0
    )

    # ── SLA: calcula em lote para chamados ativos ─────────────────
    chamados_ativos = (
        db.query(Chamado)
        .filter(
            Chamado.tenant_id == tenant.id,
            Chamado.status.in_(_ESTADOS_ATIVOS),
        )
        .all()
    )
    sla_resultados = calcular_sla_lote(chamados_ativos, db)

    sla_violados     = sum(1 for s in sla_resultados.values() if s.status == "violado")
    sla_atencao      = sum(1 for s in sla_resultados.values() if s.status == "atencao")
    sla_no_prazo     = sum(1 for s in sla_resultados.values() if s.status == "no_prazo")
    total_sla        = len(sla_resultados)
    sla_conformidade = round(sla_no_prazo / total_sla * 100) if total_sla > 0 else 100

    # Tempo médio de resolução no mês (em horas)
    import sqlalchemy as sa
    tempo_medio_resolucao = (
        db.query(
            func.avg(
                sa.cast(
                    func.extract("epoch", Chamado.data_conclusao) - func.extract("epoch", Chamado.data_abertura),
                    sa.Float
                ) / 3600
            )
        )
        .filter(
            Chamado.tenant_id == tenant.id,
            Chamado.status == StatusChamado.concluido,
            Chamado.data_conclusao.isnot(None),
            func.extract("month", Chamado.data_conclusao) == _hoje.month,
            func.extract("year",  Chamado.data_conclusao) == _hoje.year,
        )
        .scalar()
    )
    tempo_medio_h = round(float(tempo_medio_resolucao), 1) if tempo_medio_resolucao else None

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request":               request,
            "usuario":               usuario,
            "tenant":                tenant,
            "can_edit":              can_edit,
            # Patrimônio
            "total":                 total_patrimonios,
            "status_map":            status_map,
            # Financeiro
            "fat_total_hist":        float(fat_total_hist),
            "ultimo_fat":            ultimo_fat,
            "diesel_valor_mes":      float(diesel_valor_mes),
            "diesel_litros_mes":     float(diesel_litros_mes),
            "glosa_ativas":          glosa_ativas,
            "glosa_valor_mes":       float(glosa_valor_mes),
            # Operacional
            "chamados_abertos":          chamados_abertos,
            "chamados_em_atendimento":   chamados_em_atendimento,
            "chamados_concluidos_mes":   chamados_concluidos_mes,
            "preventivas_abertas":       preventivas_abertas,
            "total_filiais":             total_filiais,
            # SLA
            "sla_violados":      sla_violados,
            "sla_atencao":       sla_atencao,
            "sla_no_prazo":      sla_no_prazo,
            "total_sla":         total_sla,
            "sla_conformidade":  sla_conformidade,
            "tempo_medio_h":     tempo_medio_h,
        },
    )

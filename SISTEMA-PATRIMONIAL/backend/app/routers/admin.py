"""
Router Admin — vistas exclusivas do perfil administrador.
Gestão operacional: chamados, funcionários, usuários, cargos, filiais.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, func

from app.database import get_db
from app.models.chamado import Chamado, StatusChamado, TipoChamado
from app.models.funcionario import Funcionario
from app.models.usuario import PerfilUsuario, Usuario
from app.models.tenant import Tenant
from app.models.cargo import Cargo
from app.models.filial import Filial
from app.models.faturamento import FaturamentoHistorico
from app.models.orcamento import Orcamento, StatusOrcamento
from app.models.sla import SLAConfig
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.config_service import TenantConfigService
from app.routers._shared import brl as _brl, exigir_admin as _exigir_admin

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["brl"] = _brl


# ── Guard importado de app.routers._shared ────────────────────────────────────


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


# ── Relatório de chamados ──────────────────────────────────────────────────────

@router.get("/chamados/relatorio", response_class=HTMLResponse)
def relatorio_chamados(
    request: Request,
    mes: int = 0,
    ano: int = 0,
    tipo: str = "",
    filial_id: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    hoje = date.today()

    q = (
        db.query(Chamado)
        .options(
            joinedload(Chamado.patrimonio),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.tecnico),
            joinedload(Chamado.glosas),
        )
        .filter(Chamado.tenant_id == tenant.id)
    )
    if mes and ano:
        q = q.filter(
            extract("month", Chamado.data_abertura) == mes,
            extract("year",  Chamado.data_abertura) == ano,
        )
    elif ano:
        q = q.filter(extract("year", Chamado.data_abertura) == ano)
    if tipo:
        q = q.filter(Chamado.tipo_chamado == tipo)
    if filial_id:
        q = q.filter(Chamado.patrimonio.has(filial_id=int(filial_id)))

    q = q.filter(Chamado.status == StatusChamado.aberto)

    chamados = q.order_by(Chamado.data_abertura.desc()).limit(500).all()

    # KPIs
    total = len(chamados)
    preventivas = sum(1 for c in chamados if c.tipo_chamado == TipoChamado.preventiva)
    corretivas = sum(1 for c in chamados if c.tipo_chamado == TipoChamado.corretiva)
    sem_tipo = total - preventivas - corretivas

    def _naive(dt):
        """Remove timezone info para permitir subtração entre datetimes mistos."""
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    # Tempo médio de chegada (minutos) — apenas chamados com data_chegada_tecnico
    chegadas = [
        (_naive(c.data_chegada_tecnico) - _naive(c.data_abertura)).total_seconds() / 60
        for c in chamados
        if c.data_chegada_tecnico and c.data_abertura
    ]
    tempo_medio_chegada = round(sum(chegadas) / len(chegadas)) if chegadas else None

    # Tempo médio de resolução (horas)
    resolucoes = [
        (_naive(c.data_conclusao) - _naive(c.data_abertura)).total_seconds() / 3600
        for c in chamados
        if c.data_conclusao and c.data_abertura
    ]
    tempo_medio_resolucao = round(sum(resolucoes) / len(resolucoes), 1) if resolucoes else None

    # Com glosa
    com_glosa = sum(1 for c in chamados if c.glosas)

    # Filiais disponíveis para filtro
    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id)
        .order_by(Filial.nome)
        .all()
    )

    _MESES = [
        (1, "Jan"), (2, "Fev"), (3, "Mar"), (4, "Abr"),
        (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Ago"),
        (9, "Set"), (10, "Out"), (11, "Nov"), (12, "Dez"),
    ]
    anos = list(range(2024, hoje.year + 2))

    return templates.TemplateResponse(
        "admin/chamados_relatorio.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "chamados": chamados,
            "mes": mes,
            "ano": ano,
            "tipo": tipo,
            "filial_id": filial_id,
            "meses": _MESES,
            "anos": anos,
            "filiais": filiais,
            "kpi": {
                "total": total,
                "preventivas": preventivas,
                "corretivas": corretivas,
                "sem_tipo": sem_tipo,
                "tempo_medio_chegada": tempo_medio_chegada,
                "tempo_medio_resolucao": tempo_medio_resolucao,
                "com_glosa": com_glosa,
                "concluidos": sum(1 for c in chamados if c.status == StatusChamado.concluido),
            },
            "TipoChamado": TipoChamado,
            "StatusChamado": StatusChamado,
        },
    )


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


# ── Configurações de SLA ───────────────────────────────────────────────────────

_PRIORIDADES_ORDEM = ["critica", "alta", "media", "baixa"]


@router.get("/sla", response_class=HTMLResponse)
def admin_sla(
    request: Request,
    msg: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    configs = {
        c.prioridade: c
        for c in db.query(SLAConfig).filter(SLAConfig.tenant_id == tenant.id).all()
    }
    return templates.TemplateResponse(
        "admin/sla.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "configs": configs,
            "prioridades": _PRIORIDADES_ORDEM,
            "msg": msg,
        },
    )


@router.post("/sla")
def admin_sla_salvar(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
    critica_resposta: float = Form(...),
    critica_resolucao: float = Form(...),
    alta_resposta: float = Form(...),
    alta_resolucao: float = Form(...),
    media_resposta: float = Form(...),
    media_resolucao: float = Form(...),
    baixa_resposta: float = Form(...),
    baixa_resolucao: float = Form(...),
):
    dados = {
        "critica": (critica_resposta, critica_resolucao),
        "alta":    (alta_resposta, alta_resolucao),
        "media":   (media_resposta, media_resolucao),
        "baixa":   (baixa_resposta, baixa_resolucao),
    }
    for prioridade, (resposta, resolucao) in dados.items():
        if resposta <= 0 or resolucao <= 0:
            raise HTTPException(status_code=400, detail=f"Prazos devem ser maiores que zero para '{prioridade}'.")
        if resolucao < resposta:
            raise HTTPException(status_code=400, detail=f"Prazo de resolução não pode ser menor que o de resposta para '{prioridade}'.")
        cfg = db.query(SLAConfig).filter(
            SLAConfig.tenant_id == tenant.id,
            SLAConfig.prioridade == prioridade,
        ).first()
        if cfg:
            cfg.prazo_resposta_horas = resposta
            cfg.prazo_resolucao_horas = resolucao
        else:
            db.add(SLAConfig(
                tenant_id=tenant.id,
                prioridade=prioridade,
                prazo_resposta_horas=resposta,
                prazo_resolucao_horas=resolucao,
            ))
    db.commit()
    return RedirectResponse(url="/admin/sla?msg=salvo", status_code=303)


@router.post("/sla/resetar")
def admin_sla_resetar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """Remove as configs customizadas — o sistema voltará a usar os padrões embutidos."""
    db.query(SLAConfig).filter(SLAConfig.tenant_id == tenant.id).delete()
    db.commit()
    return RedirectResponse(url="/admin/sla?msg=resetado", status_code=303)


# ── Integrações (Claude / LLM) ────────────────────────────────────────────────


@router.get("/integracoes", response_class=HTMLResponse)
def admin_integracoes(
    request: Request,
    msg: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    svc = TenantConfigService(tenant)
    return templates.TemplateResponse(
        "admin/integracoes.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "chave_mascarada": svc.get_llm_api_key_masked(),
            "tem_chave": svc.has_llm_api_key(),
            "msg": msg,
        },
    )


@router.post("/integracoes")
def admin_integracoes_salvar(
    request: Request,
    acao: str = Form(...),
    api_key: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    svc = TenantConfigService(tenant)
    if acao == "salvar":
        try:
            svc.set_llm_api_key(db, api_key or "")
        except ValueError as exc:
            return templates.TemplateResponse(
                "admin/integracoes.html",
                {
                    "request": request,
                    "usuario": usuario,
                    "tenant": tenant,
                    "chave_mascarada": svc.get_llm_api_key_masked(),
                    "tem_chave": svc.has_llm_api_key(),
                    "msg": f"erro:{exc}",
                },
                status_code=400,
            )
        return RedirectResponse(url="/admin/integracoes?msg=salvo", status_code=303)
    elif acao == "remover":
        svc.remove_llm_api_key(db)
        return RedirectResponse(url="/admin/integracoes?msg=removido", status_code=303)
    raise HTTPException(status_code=400, detail="Ação inválida.")


# ── Faturamento por Unidades ───────────────────────────────────────────────────

_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


@router.get("/faturamento", response_class=HTMLResponse)
def admin_faturamento(
    request: Request,
    mes: int = 0,
    ano: int = 0,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    hoje = date.today()
    if not mes:
        mes = hoje.month
    if not ano:
        ano = hoje.year

    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )

    resultado = []
    total_geral = {
        "chamados": 0,
        "mao_obra": Decimal("0"),
        "pecas": Decimal("0"),
        "total": Decimal("0"),
    }

    for filial in filiais:
        chamados_filial = (
            db.query(Chamado)
            .filter(
                Chamado.tenant_id == tenant.id,
                Chamado.filial_id == filial.id,
                Chamado.status == StatusChamado.concluido,
                extract("month", Chamado.data_conclusao) == mes,
                extract("year", Chamado.data_conclusao) == ano,
            )
            .all()
        )
        chamado_ids = [c.id for c in chamados_filial]

        mao_obra = Decimal("0")
        pecas = Decimal("0")
        if chamado_ids:
            orcamentos = (
                db.query(Orcamento)
                .filter(
                    Orcamento.chamado_id.in_(chamado_ids),
                    Orcamento.status == StatusOrcamento.aprovado,
                )
                .all()
            )
            for o in orcamentos:
                mao_obra += o.valor_mao_obra or Decimal("0")
                pecas += o.valor_pecas or Decimal("0")

        total_filial = mao_obra + pecas
        resultado.append({
            "filial": filial,
            "chamados": len(chamados_filial),
            "mao_obra": mao_obra,
            "pecas": pecas,
            "total": total_filial,
        })
        total_geral["chamados"] += len(chamados_filial)
        total_geral["mao_obra"] += mao_obra
        total_geral["pecas"] += pecas
        total_geral["total"] += total_filial

    # Chamados sem filial vinculada
    sem_filial = (
        db.query(Chamado)
        .filter(
            Chamado.tenant_id == tenant.id,
            Chamado.filial_id.is_(None),
            Chamado.status == StatusChamado.concluido,
            extract("month", Chamado.data_conclusao) == mes,
            extract("year", Chamado.data_conclusao) == ano,
        )
        .all()
    )
    if sem_filial:
        sf_ids = [c.id for c in sem_filial]
        sf_mao = Decimal("0")
        sf_pecas = Decimal("0")
        orcamentos_sf = (
            db.query(Orcamento)
            .filter(
                Orcamento.chamado_id.in_(sf_ids),
                Orcamento.status == StatusOrcamento.aprovado,
            )
            .all()
        )
        for o in orcamentos_sf:
            sf_mao += o.valor_mao_obra or Decimal("0")
            sf_pecas += o.valor_pecas or Decimal("0")
        sf_total = sf_mao + sf_pecas
        resultado.append({
            "filial": None,
            "chamados": len(sem_filial),
            "mao_obra": sf_mao,
            "pecas": sf_pecas,
            "total": sf_total,
        })
        total_geral["chamados"] += len(sem_filial)
        total_geral["mao_obra"] += sf_mao
        total_geral["pecas"] += sf_pecas
        total_geral["total"] += sf_total

    anos_disponiveis = list(range(2022, hoje.year + 2))

    # Histórico fechado para o período exibido
    historico = (
        db.query(FaturamentoHistorico)
        .filter(
            FaturamentoHistorico.tenant_id == str(tenant.id),
            FaturamentoHistorico.mes == mes,
            FaturamentoHistorico.ano == ano,
        )
        .order_by(FaturamentoHistorico.filial_nome)
        .all()
    )
    periodo_fechado = any(h.origem == "sistema" for h in historico)

    return templates.TemplateResponse(
        "admin/faturamento.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "resultado": resultado,
            "total_geral": total_geral,
            "mes": mes,
            "ano": ano,
            "anos_disponiveis": anos_disponiveis,
            "meses": _MESES,
            "historico": historico,
            "periodo_fechado": periodo_fechado,
        },
    )


@router.post("/faturamento/fechar")
def fechar_periodo_faturamento(
    mes: int = Form(...),
    ano: int = Form(...),
    observacoes: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """
    Cria snapshots imutáveis do faturamento calculado para o período informado.
    Cada unidade (filial) vira um registro em faturamento_historico.
    """
    if not (1 <= mes <= 12) or ano < 2020:
        raise HTTPException(status_code=400, detail="Período inválido.")

    # Verifica se já foi fechado
    existente = db.query(FaturamentoHistorico).filter(
        FaturamentoHistorico.tenant_id == str(tenant.id),
        FaturamentoHistorico.mes == mes,
        FaturamentoHistorico.ano == ano,
        FaturamentoHistorico.origem == "sistema",
    ).first()
    if existente:
        raise HTTPException(
            status_code=409,
            detail=f"Faturamento {mes:02d}/{ano} já foi fechado. Exclua antes de re-fechar.",
        )

    # Coleta dados por filial (reusa a mesma lógica da view GET)
    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )

    # Funcionário vinculado ao usuário logado (para audit)
    func = db.query(Funcionario).filter(
        Funcionario.tenant_id == tenant.id,
        Funcionario.usuario_id == usuario.id,
    ).first() if hasattr(Funcionario, "usuario_id") else None

    registros = []

    def _coletar(filial_obj, filial_nome_str):
        filtro_filial = (
            Chamado.filial_id == filial_obj.id
            if filial_obj
            else Chamado.filial_id.is_(None)
        )
        chamados_filial = db.query(Chamado).filter(
            Chamado.tenant_id == tenant.id,
            filtro_filial,
            Chamado.status == StatusChamado.concluido,
            extract("month", Chamado.data_conclusao) == mes,
            extract("year", Chamado.data_conclusao) == ano,
        ).all()

        chamado_ids = [c.id for c in chamados_filial]
        mao_obra = Decimal("0")
        pecas = Decimal("0")
        if chamado_ids:
            for o in db.query(Orcamento).filter(
                Orcamento.chamado_id.in_(chamado_ids),
                Orcamento.status == StatusOrcamento.aprovado,
            ).all():
                mao_obra += o.valor_mao_obra or Decimal("0")
                pecas += o.valor_pecas or Decimal("0")

        return FaturamentoHistorico(
            tenant_id=str(tenant.id),
            filial_id=filial_obj.id if filial_obj else None,
            filial_nome=filial_nome_str,
            mes=mes,
            ano=ano,
            chamados_count=len(chamados_filial),
            valor_mao_obra=mao_obra,
            valor_pecas=pecas,
            valor_total=mao_obra + pecas,
            observacoes=observacoes or None,
            origem="sistema",
            fechado_por_id=func.id if func else None,
            fechado_em=datetime.utcnow(),
        )

    for filial in filiais:
        registros.append(_coletar(filial, filial.nome))

    # Chamados sem filial
    sem_filial_chamados = db.query(Chamado).filter(
        Chamado.tenant_id == tenant.id,
        Chamado.filial_id.is_(None),
        Chamado.status == StatusChamado.concluido,
        extract("month", Chamado.data_conclusao) == mes,
        extract("year", Chamado.data_conclusao) == ano,
    ).count()
    if sem_filial_chamados:
        registros.append(_coletar(None, "Sem unidade vinculada"))

    for r in registros:
        db.add(r)
    db.commit()

    return RedirectResponse(
        url=f"/admin/faturamento?mes={mes}&ano={ano}&msg=fechado",
        status_code=303,
    )


@router.post("/faturamento/reabrir")
def reabrir_periodo_faturamento(
    mes: int = Form(...),
    ano: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """Remove todos os snapshots 'sistema' do período — permite re-fechar."""
    deletados = (
        db.query(FaturamentoHistorico)
        .filter(
            FaturamentoHistorico.tenant_id == str(tenant.id),
            FaturamentoHistorico.mes == mes,
            FaturamentoHistorico.ano == ano,
            FaturamentoHistorico.origem == "sistema",
        )
        .delete()
    )
    db.commit()
    return RedirectResponse(
        url=f"/admin/faturamento?mes={mes}&ano={ano}&msg=reaberto",
        status_code=303,
    )


@router.get("/faturamento/historico", response_class=HTMLResponse)
def admin_faturamento_historico(
    request: Request,
    filial_id: str = "",
    ano: int = 0,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    hoje = date.today()
    if not ano:
        ano = hoje.year

    q = (
        db.query(FaturamentoHistorico)
        .filter(
            FaturamentoHistorico.tenant_id == str(tenant.id),
            FaturamentoHistorico.ano == ano,
        )
    )
    if filial_id:
        q = q.filter(FaturamentoHistorico.filial_id == int(filial_id))

    registros = q.order_by(
        FaturamentoHistorico.mes.desc(),
        FaturamentoHistorico.filial_nome,
    ).all()

    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id)
        .order_by(Filial.nome)
        .all()
    )
    anos_disponiveis = list(range(2022, hoje.year + 2))

    return templates.TemplateResponse(
        "admin/faturamento_historico.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "registros": registros,
            "filiais": filiais,
            "filial_id": filial_id,
            "ano": ano,
            "anos_disponiveis": anos_disponiveis,
            "meses": _MESES,
        },
    )


@router.get("/faturamento/relatorio", response_class=HTMLResponse)
def admin_faturamento_relatorio(
    request: Request,
    ano: int = 0,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    """
    Relatório anual matricial: linhas = unidades, colunas = meses.
    Consolida origem 'sistema' (prioritária) e 'importacao' no mesmo período.
    """
    hoje = date.today()
    if not ano:
        ano = hoje.year

    registros = (
        db.query(FaturamentoHistorico)
        .filter(
            FaturamentoHistorico.tenant_id == str(tenant.id),
            FaturamentoHistorico.ano == ano,
        )
        .order_by(FaturamentoHistorico.filial_nome, FaturamentoHistorico.mes)
        .all()
    )

    # Monta dicionário {filial_nome: {mes: dado}} — "sistema" sobrepõe "importacao"
    matriz: dict[str, dict[int, dict]] = {}
    for r in registros:
        if r.filial_nome not in matriz:
            matriz[r.filial_nome] = {}
        existente = matriz[r.filial_nome].get(r.mes)
        if not existente or r.origem == "sistema":
            matriz[r.filial_nome][r.mes] = {
                "chamados": r.chamados_count,
                "mao_obra": float(r.valor_mao_obra or 0),
                "pecas": float(r.valor_pecas or 0),
                "total": float(r.valor_total or 0),
                "origem": r.origem,
            }

    # Linhas: cada unidade com todos os 12 meses (None se não houver dado)
    unidades_nomes = sorted(matriz.keys())
    linhas = []
    for nome in unidades_nomes:
        meses_data = [matriz[nome].get(m) for m in range(1, 13)]
        total_chamados = sum(d["chamados"] for d in meses_data if d)
        total_valor = sum(d["total"] for d in meses_data if d)
        linhas.append({
            "nome": nome,
            "meses": meses_data,           # lista[12]: dict ou None
            "total_chamados": total_chamados,
            "total_valor": total_valor,
            "ticket_medio": total_valor / total_chamados if total_chamados else 0,
        })

    # Totais por coluna (por mês)
    totais_mes = []
    for m_idx in range(12):
        vals = [l["meses"][m_idx] for l in linhas if l["meses"][m_idx]]
        totais_mes.append({
            "chamados": sum(d["chamados"] for d in vals),
            "total": sum(d["total"] for d in vals),
        })

    total_anual_chamados = sum(t["chamados"] for t in totais_mes)
    total_anual_valor = sum(t["total"] for t in totais_mes)

    # Meses que têm dados (para highlighting)
    meses_com_dados = {m + 1 for m in range(12) if totais_mes[m]["total"] > 0}

    anos_disponiveis = list(range(2022, hoje.year + 2))

    return templates.TemplateResponse(
        "admin/faturamento_relatorio.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "ano": ano,
            "anos_disponiveis": anos_disponiveis,
            "meses": _MESES,
            "linhas": linhas,
            "totais_mes": totais_mes,
            "total_anual_chamados": total_anual_chamados,
            "total_anual_valor": total_anual_valor,
            "meses_com_dados": meses_com_dados,
        },
    )


# ─────────────────────────────────────────────────────────────
# DRE — Demonstrativo de Faturamento por Unidade
# ─────────────────────────────────────────────────────────────

@router.get("/dre", response_class=HTMLResponse)
def admin_dre(
    request: Request,
    ano: int = None,
    filial_nome: str = "",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    _exigir_admin(usuario)

    hoje = date.today()
    if not ano:
        ano = hoje.year

    anos_disponiveis = list(range(2022, hoje.year + 2))

    # Lista de unidades disponíveis
    unidades_rows = (
        db.query(FaturamentoHistorico.filial_nome)
        .filter(FaturamentoHistorico.tenant_id == tenant.id)
        .distinct()
        .order_by(FaturamentoHistorico.filial_nome)
        .all()
    )
    unidades = [r[0] for r in unidades_rows]

    def _query_ano(ano_alvo: int, nome_filtro: str):
        q = (
            db.query(
                FaturamentoHistorico.mes,
                func.sum(FaturamentoHistorico.valor_mao_obra).label("mao_obra"),
                func.sum(FaturamentoHistorico.valor_pecas).label("pecas"),
                func.sum(FaturamentoHistorico.valor_total).label("total"),
                func.sum(FaturamentoHistorico.chamados_count).label("chamados"),
            )
            .filter(
                FaturamentoHistorico.tenant_id == tenant.id,
                FaturamentoHistorico.ano == ano_alvo,
            )
        )
        if nome_filtro:
            q = q.filter(FaturamentoHistorico.filial_nome == nome_filtro)
        return q.group_by(FaturamentoHistorico.mes).order_by(FaturamentoHistorico.mes).all()

    rows_ano = _query_ano(ano, filial_nome)
    rows_ant = _query_ano(ano - 1, filial_nome)

    # Monta dicts indexados por mês
    def _por_mes(rows):
        d = {}
        for r in rows:
            mao_obra = float(r.mao_obra or 0)
            pecas    = float(r.pecas or 0)
            total    = float(r.total or 0)
            chams    = int(r.chamados or 0)
            d[r.mes] = {
                "mao_obra": mao_obra,
                "pecas":    pecas,
                "total":    total,
                "chamados": chams,
                "ticket":   round(total / chams, 2) if chams else 0.0,
            }
        return d

    dados_ano = _por_mes(rows_ano)
    dados_ant = _por_mes(rows_ant)

    # Linhas mensais enriquecidas com comparativo
    linhas = []
    for m in range(1, 13):
        atual = dados_ano.get(m, {"mao_obra": 0, "pecas": 0, "total": 0, "chamados": 0, "ticket": 0})
        ant   = dados_ant.get(m, {"mao_obra": 0, "pecas": 0, "total": 0, "chamados": 0, "ticket": 0})
        var   = None
        if ant["total"] > 0:
            var = round((atual["total"] - ant["total"]) / ant["total"] * 100, 1)
        linhas.append({
            "mes":       m,
            "mes_nome":  _MESES[m],
            "mao_obra":  atual["mao_obra"],
            "pecas":     atual["pecas"],
            "total":     atual["total"],
            "chamados":  atual["chamados"],
            "ticket":    atual["ticket"],
            "ant_total": ant["total"],
            "variacao":  var,
            "tem_dados": atual["total"] > 0,
        })

    # Totais anuais
    total_ano = {
        "mao_obra":  sum(l["mao_obra"] for l in linhas),
        "pecas":     sum(l["pecas"]    for l in linhas),
        "total":     sum(l["total"]    for l in linhas),
        "chamados":  sum(l["chamados"] for l in linhas),
    }
    total_ano["ticket"] = round(total_ano["total"] / total_ano["chamados"], 2) if total_ano["chamados"] else 0.0
    total_ant = sum(l["ant_total"] for l in linhas)
    total_ano["variacao"] = (
        round((total_ano["total"] - total_ant) / total_ant * 100, 1)
        if total_ant > 0 else None
    )

    # Se filtrado por unidade: ranking das demais unidades no mesmo ano para contexto
    ranking = []
    if not filial_nome:
        rank_rows = (
            db.query(
                FaturamentoHistorico.filial_nome,
                func.sum(FaturamentoHistorico.valor_total).label("total"),
                func.sum(FaturamentoHistorico.chamados_count).label("chamados"),
            )
            .filter(
                FaturamentoHistorico.tenant_id == tenant.id,
                FaturamentoHistorico.ano == ano,
            )
            .group_by(FaturamentoHistorico.filial_nome)
            .order_by(func.sum(FaturamentoHistorico.valor_total).desc())
            .limit(10)
            .all()
        )
        ranking = [{"nome": r.filial_nome, "total": float(r.total or 0), "chamados": int(r.chamados or 0)} for r in rank_rows]

    return templates.TemplateResponse(
        "admin/dre.html",
        {
            "request":          request,
            "usuario":          usuario,
            "tenant":           tenant,
            "ano":              ano,
            "ano_anterior":     ano - 1,
            "anos_disponiveis": anos_disponiveis,
            "filial_nome":      filial_nome,
            "unidades":         unidades,
            "linhas":           linhas,
            "total_ano":        total_ano,
            "total_ant":        total_ant,
            "ranking":          ranking,
            "meses":            _MESES,
        },
    )

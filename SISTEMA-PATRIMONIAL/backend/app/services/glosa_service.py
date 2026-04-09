"""
glosa_service.py — Lógica de cálculo e gestão do módulo de Glosa.

Responsabilidades:
  - calcular_percentual()    : determina % de penalidade com base nas faixas configuradas
  - calcular_horas()         : diferença em horas entre dois datetimes
  - seed_faixas_padrao()     : insere as 5 faixas padrão Polsec para um tenant
  - abrir_glosa()            : cria registro com status 'ativa'
  - encerrar_glosa()         : define data_fim, calcula horas + percentual + valor
  - listar_glosas()          : consulta paginada com filtros opcionais
  - resumo_glosa_periodo()   : agrega por filial num período (para relatório)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.glosa import GlosaChamado, GlosaFaixa, StatusGlosa


# ── Faixas padrão Polsec (conforme "Quadro de Glosa" da planilha) ─────────────

FAIXAS_PADRAO = [
    {"horas_min": Decimal("1"),   "horas_max": Decimal("24"),  "percentual": Decimal("2")},
    {"horas_min": Decimal("24"),  "horas_max": Decimal("60"),  "percentual": Decimal("4")},
    {"horas_min": Decimal("60"),  "horas_max": Decimal("168"), "percentual": Decimal("8")},
    {"horas_min": Decimal("168"), "horas_max": Decimal("240"), "percentual": Decimal("16")},
    {"horas_min": Decimal("240"), "horas_max": None,           "percentual": Decimal("32")},
]


def seed_faixas_padrao(tenant_id: str, db: Session) -> int:
    """Insere as faixas padrão Polsec para o tenant (ignora se já existir).
    Retorna quantas foram inseridas."""
    inseridas = 0
    for f in FAIXAS_PADRAO:
        existe = db.query(GlosaFaixa).filter(
            GlosaFaixa.tenant_id == tenant_id,
            GlosaFaixa.horas_min == f["horas_min"],
        ).first()
        if not existe:
            db.add(GlosaFaixa(tenant_id=tenant_id, **f))
            inseridas += 1
    db.commit()
    return inseridas


# ── Cálculo ───────────────────────────────────────────────────────────────────

def calcular_horas(inicio: datetime, fim: datetime) -> Decimal:
    """Retorna a diferença em horas (2 casas decimais) entre dois datetimes."""
    delta = fim - inicio
    horas = Decimal(str(delta.total_seconds())) / Decimal("3600")
    return horas.quantize(Decimal("0.01"))


def calcular_percentual(horas: Decimal, tenant_id: str, db: Session) -> Optional[Decimal]:
    """
    Retorna o percentual de glosa correspondente à quantidade de horas,
    conforme a tabela glosa_faixas do tenant.
    Retorna None se não houver faixa configurada ou horas < mínimo.
    """
    faixas = (
        db.query(GlosaFaixa)
        .filter(GlosaFaixa.tenant_id == tenant_id, GlosaFaixa.ativo == True)
        .order_by(GlosaFaixa.horas_min)
        .all()
    )
    for faixa in faixas:
        if horas >= faixa.horas_min and (faixa.horas_max is None or horas < faixa.horas_max):
            return faixa.percentual
    return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def abrir_glosa(
    *,
    tenant_id: str,
    filial_nome: str,
    data_inicio: datetime,
    motivo: str,
    registrado_por_id: int,
    chamado_id: Optional[int] = None,
    filial_id: Optional[int] = None,
    valor_base: Optional[Decimal] = None,
    observacoes: Optional[str] = None,
    db: Session,
) -> GlosaChamado:
    """Cria um novo registro de glosa com status 'ativa'."""
    glosa = GlosaChamado(
        tenant_id=tenant_id,
        chamado_id=chamado_id,
        filial_id=filial_id,
        filial_nome=filial_nome,
        data_inicio=data_inicio,
        motivo=motivo,
        valor_base=valor_base,
        observacoes=observacoes,
        registrado_por_id=registrado_por_id,
        status=StatusGlosa.ativa,
    )
    db.add(glosa)
    db.commit()
    db.refresh(glosa)
    return glosa


def encerrar_glosa(
    glosa_id: int,
    tenant_id: str,
    data_fim: datetime,
    encerrado_por_id: int,
    db: Session,
    observacoes: Optional[str] = None,
) -> GlosaChamado:
    """
    Encerra uma glosa ativa:
      1. Define data_fim
      2. Calcula horas_indisponiveis
      3. Busca percentual nas faixas do tenant
      4. Calcula valor_glosa = valor_base × percentual/100 (se valor_base informado)
    """
    glosa = (
        db.query(GlosaChamado)
        .filter(GlosaChamado.id == glosa_id, GlosaChamado.tenant_id == tenant_id)
        .first()
    )
    if not glosa:
        raise ValueError(f"Glosa #{glosa_id} não encontrada para este tenant.")
    if glosa.status != StatusGlosa.ativa:
        raise ValueError(f"Glosa #{glosa_id} não está ativa (status atual: {glosa.status}).")

    horas = calcular_horas(glosa.data_inicio, data_fim)
    percentual = calcular_percentual(horas, tenant_id, db)
    valor_glosa = None
    if percentual is not None and glosa.valor_base:
        valor_glosa = (glosa.valor_base * percentual / Decimal("100")).quantize(Decimal("0.01"))

    glosa.data_fim            = data_fim
    glosa.horas_indisponiveis = horas
    glosa.percentual_glosa    = percentual
    glosa.valor_glosa         = valor_glosa
    glosa.status              = StatusGlosa.encerrada
    glosa.encerrado_por_id    = encerrado_por_id
    glosa.updated_at          = datetime.utcnow()
    if observacoes:
        glosa.observacoes = observacoes

    db.commit()
    db.refresh(glosa)
    return glosa


def listar_glosas(
    tenant_id: str,
    db: Session,
    *,
    status: Optional[str] = None,
    filial_id: Optional[int] = None,
    filial_nome: Optional[str] = None,
    ano: Optional[int] = None,
    mes: Optional[int] = None,
    page: int = 1,
    per_page: int = 50,
):
    """Retorna (items, total) de glosas com filtros opcionais."""
    q = db.query(GlosaChamado).filter(GlosaChamado.tenant_id == tenant_id)

    if status:
        q = q.filter(GlosaChamado.status == status)
    if filial_id:
        q = q.filter(GlosaChamado.filial_id == filial_id)
    if filial_nome:
        q = q.filter(GlosaChamado.filial_nome.ilike(f"%{filial_nome}%"))
    if ano:
        q = q.filter(func.extract("year", GlosaChamado.data_inicio) == ano)
    if mes:
        q = q.filter(func.extract("month", GlosaChamado.data_inicio) == mes)

    total = q.count()
    items = (
        q.order_by(GlosaChamado.data_inicio.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def resumo_glosa_periodo(
    tenant_id: str,
    db: Session,
    ano: Optional[int] = None,
    mes: Optional[int] = None,
) -> list[dict]:
    """
    Agrega glosas encerradas por filial para um período (ano/mês).
    Retorna lista de dicts: filial_nome, qtd, horas_total, valor_total.
    Ordenado por valor_total DESC.
    """
    q = (
        db.query(
            GlosaChamado.filial_nome,
            func.count(GlosaChamado.id).label("qtd"),
            func.sum(GlosaChamado.horas_indisponiveis).label("horas_total"),
            func.sum(GlosaChamado.valor_glosa).label("valor_total"),
        )
        .filter(
            GlosaChamado.tenant_id == tenant_id,
            GlosaChamado.status == StatusGlosa.encerrada,
        )
    )
    if ano:
        q = q.filter(func.extract("year", GlosaChamado.data_inicio) == ano)
    if mes:
        q = q.filter(func.extract("month", GlosaChamado.data_inicio) == mes)

    rows = (
        q.group_by(GlosaChamado.filial_nome)
        .order_by(func.sum(GlosaChamado.valor_glosa).desc().nullslast())
        .all()
    )
    return [
        {
            "filial_nome":  r.filial_nome,
            "qtd":          r.qtd,
            "horas_total":  float(r.horas_total or 0),
            "valor_total":  float(r.valor_total or 0),
        }
        for r in rows
    ]

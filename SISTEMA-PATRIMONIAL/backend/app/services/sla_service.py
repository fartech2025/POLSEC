"""
SLA Service — calcula status de SLA para cada chamado.

Status possíveis:
  no_prazo   : tempo decorrido < 80% do prazo
  atencao    : 80% ≤ tempo decorrido < 100%
  violado    : tempo decorrido ≥ 100% do prazo (ou já concluído fora do prazo)
  concluido  : chamado encerrado dentro do prazo
  sem_sla    : sem configuração de SLA para esta prioridade
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.chamado import Chamado, StatusChamado
from app.models.sla import SLAConfig

# Prazos padrão (horas) usados quando o tenant não tem SLA configurado
_DEFAULTS: dict[str, tuple[float, float]] = {
    #                 resposta  resolução
    "critica": (1.0,   4.0),
    "alta":    (4.0,  24.0),
    "media":   (8.0,  48.0),
    "baixa":   (24.0, 96.0),
}


@dataclass
class SLAStatus:
    status: str           # no_prazo | atencao | violado | concluido_ok | concluido_violado | sem_sla
    label: str            # texto legível
    cor: str              # Bootstrap color class: success | warning | danger | secondary
    percentual: float     # 0–100+ (pode ultrapassar 100 quando violado)
    horas_decorridas: float
    prazo_resolucao_horas: float
    prazo_resposta_horas: float
    horas_restantes: float   # negativo se violado


def _horas_desde(inicio: datetime) -> float:
    agora = datetime.now(tz=timezone.utc)
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    return (agora - inicio).total_seconds() / 3600


def calcular_sla(chamado: Chamado, db: Session) -> SLAStatus:
    """Retorna o SLAStatus de um chamado."""
    prioridade = chamado.prioridade.value if hasattr(chamado.prioridade, "value") else chamado.prioridade

    # Busca configuração do tenant ou usa padrão
    cfg: Optional[SLAConfig] = db.query(SLAConfig).filter(
        SLAConfig.tenant_id == chamado.tenant_id,
        SLAConfig.prioridade == prioridade,
        SLAConfig.ativo == True,
    ).first()

    if cfg:
        prazo_resposta = cfg.prazo_resposta_horas
        prazo_resolucao = cfg.prazo_resolucao_horas
    elif prioridade in _DEFAULTS:
        prazo_resposta, prazo_resolucao = _DEFAULTS[prioridade]
    else:
        return SLAStatus(
            status="sem_sla", label="Sem SLA", cor="secondary",
            percentual=0, horas_decorridas=0,
            prazo_resolucao_horas=0, prazo_resposta_horas=0, horas_restantes=0,
        )

    horas = _horas_desde(chamado.data_abertura)
    percentual = (horas / prazo_resolucao * 100) if prazo_resolucao > 0 else 0
    horas_restantes = prazo_resolucao - horas

    # Chamado já encerrado
    is_encerrado = chamado.status in (StatusChamado.concluido, StatusChamado.cancelado, StatusChamado.rejeitado)
    if is_encerrado and chamado.data_conclusao:
        horas_reais = (
            (chamado.data_conclusao.replace(tzinfo=timezone.utc) if chamado.data_conclusao.tzinfo is None
             else chamado.data_conclusao) - 
            (chamado.data_abertura.replace(tzinfo=timezone.utc) if chamado.data_abertura.tzinfo is None
             else chamado.data_abertura)
        ).total_seconds() / 3600
        dentro = horas_reais <= prazo_resolucao
        return SLAStatus(
            status="concluido_ok" if dentro else "concluido_violado",
            label="Concluído no prazo" if dentro else "Concluído fora do prazo",
            cor="success" if dentro else "danger",
            percentual=min(horas_reais / prazo_resolucao * 100, 200) if prazo_resolucao else 0,
            horas_decorridas=horas_reais,
            prazo_resolucao_horas=prazo_resolucao,
            prazo_resposta_horas=prazo_resposta,
            horas_restantes=prazo_resolucao - horas_reais,
        )

    # Chamado em aberto: calcula status atual
    if percentual >= 100:
        status, label, cor = "violado", "SLA Violado", "danger"
    elif percentual >= 80:
        status, label, cor = "atencao", "SLA em Risco", "warning"
    else:
        status, label, cor = "no_prazo", "Dentro do Prazo", "success"

    return SLAStatus(
        status=status, label=label, cor=cor,
        percentual=min(percentual, 200),
        horas_decorridas=horas,
        prazo_resolucao_horas=prazo_resolucao,
        prazo_resposta_horas=prazo_resposta,
        horas_restantes=horas_restantes,
    )


def calcular_sla_lote(chamados: list[Chamado], db: Session) -> dict[int, SLAStatus]:
    """Calcula SLA para uma lista de chamados, retornando dict {chamado_id: SLAStatus}."""
    # Carrega todas as configs do tenant de uma vez (evita N+1)
    if not chamados:
        return {}
    tenant_id = chamados[0].tenant_id
    configs = {
        c.prioridade: c
        for c in db.query(SLAConfig).filter(
            SLAConfig.tenant_id == tenant_id,
            SLAConfig.ativo == True,
        ).all()
    }

    resultado: dict[int, SLAStatus] = {}
    for chamado in chamados:
        prioridade = chamado.prioridade.value if hasattr(chamado.prioridade, "value") else chamado.prioridade
        cfg = configs.get(prioridade)

        if cfg:
            prazo_resposta = cfg.prazo_resposta_horas
            prazo_resolucao = cfg.prazo_resolucao_horas
        elif prioridade in _DEFAULTS:
            prazo_resposta, prazo_resolucao = _DEFAULTS[prioridade]
        else:
            resultado[chamado.id] = SLAStatus(
                status="sem_sla", label="Sem SLA", cor="secondary",
                percentual=0, horas_decorridas=0,
                prazo_resolucao_horas=0, prazo_resposta_horas=0, horas_restantes=0,
            )
            continue

        horas = _horas_desde(chamado.data_abertura)
        percentual = (horas / prazo_resolucao * 100) if prazo_resolucao > 0 else 0
        horas_restantes = prazo_resolucao - horas

        is_encerrado = chamado.status in (StatusChamado.concluido, StatusChamado.cancelado, StatusChamado.rejeitado)
        if is_encerrado and chamado.data_conclusao:
            dc = chamado.data_conclusao
            da = chamado.data_abertura
            if dc.tzinfo is None: dc = dc.replace(tzinfo=timezone.utc)
            if da.tzinfo is None: da = da.replace(tzinfo=timezone.utc)
            horas_reais = (dc - da).total_seconds() / 3600
            dentro = horas_reais <= prazo_resolucao
            resultado[chamado.id] = SLAStatus(
                status="concluido_ok" if dentro else "concluido_violado",
                label="Concluído no prazo" if dentro else "Concluído fora do prazo",
                cor="success" if dentro else "danger",
                percentual=min(horas_reais / prazo_resolucao * 100, 200) if prazo_resolucao else 0,
                horas_decorridas=horas_reais,
                prazo_resolucao_horas=prazo_resolucao,
                prazo_resposta_horas=prazo_resposta,
                horas_restantes=prazo_resolucao - horas_reais,
            )
            continue

        if percentual >= 100:
            st, lb, co = "violado", "SLA Violado", "danger"
        elif percentual >= 80:
            st, lb, co = "atencao", "SLA em Risco", "warning"
        else:
            st, lb, co = "no_prazo", "Dentro do Prazo", "success"

        resultado[chamado.id] = SLAStatus(
            status=st, label=lb, cor=co,
            percentual=min(percentual, 200),
            horas_decorridas=horas,
            prazo_resolucao_horas=prazo_resolucao,
            prazo_resposta_horas=prazo_resposta,
            horas_restantes=horas_restantes,
        )

    return resultado


def seed_sla_padrao(tenant_id: str, db: Session) -> None:
    """Cria as configs padrão de SLA para um tenant (idempotente)."""
    for prioridade, (resposta, resolucao) in _DEFAULTS.items():
        existe = db.query(SLAConfig).filter(
            SLAConfig.tenant_id == tenant_id,
            SLAConfig.prioridade == prioridade,
        ).first()
        if not existe:
            db.add(SLAConfig(
                tenant_id=tenant_id,
                prioridade=prioridade,
                prazo_resposta_horas=resposta,
                prazo_resolucao_horas=resolucao,
            ))
    db.commit()

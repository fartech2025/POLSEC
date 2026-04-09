"""
Glosa — Módulo de penalidade contratual por indisponibilidade.

Estrutura:
  GlosaFaixa      : tabela de percentuais por faixa de horas (configurável por tenant)
  GlosaChamado    : registro individual de glosa vinculado a um chamado
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Numeric,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class StatusGlosa(str, enum.Enum):
    ativa      = "ativa"
    encerrada  = "encerrada"
    contestada = "contestada"
    cancelada  = "cancelada"


class GlosaFaixa(Base):
    """
    Faixas de percentual de penalidade por horas de indisponibilidade.

    Padrão Polsec:
        1–24h   → 2%
        24–60h  → 4%
        60–168h → 8%
        168–240h→ 16%
        >240h   → 32%
    """
    __tablename__ = "glosa_faixas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "horas_min", name="uq_glosa_faixas_tenant_min"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    tenant_id  = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    horas_min  = Column(Numeric(8, 2), nullable=False)   # limite inferior (inclusivo)
    horas_max  = Column(Numeric(8, 2), nullable=True)    # NULL = sem limite (última faixa)
    percentual = Column(Numeric(5, 2), nullable=False)   # ex: 2.00, 4.00, 8.00…

    ativo      = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")


class GlosaChamado(Base):
    """
    Registro de glosa (penalidade) por período de indisponibilidade.
    Vinculado opcionalmente a um chamado existente.
    O valor da penalidade é calculado pelo glosa_service ao encerrar.
    """
    __tablename__ = "glosa_chamados"

    id        = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Vínculos (opcionais para permitir lançamento manual retroativo)
    chamado_id = Column(Integer, ForeignKey("chamados.id", ondelete="SET NULL"), nullable=True)
    filial_id  = Column(Integer, ForeignKey("filiais.id", ondelete="SET NULL"), nullable=True)
    filial_nome = Column(String(150), nullable=False)   # snapshot — não perde nome histórico

    # Período de indisponibilidade
    data_inicio         = Column(DateTime, nullable=False)
    data_fim            = Column(DateTime, nullable=True)   # NULL = ainda ativa
    horas_indisponiveis = Column(Numeric(8, 2), nullable=True)   # calculado ao encerrar

    # Resultado financeiro
    percentual_glosa = Column(Numeric(5, 2), nullable=True)    # 2 | 4 | 8 | 16 | 32
    valor_base       = Column(Numeric(12, 2), nullable=True)   # valor mensal do contrato
    valor_glosa      = Column(Numeric(12, 2), nullable=True)   # valor_base × percentual/100

    # Controle
    status      = Column(String(20), default=StatusGlosa.ativa, nullable=False, index=True)
    motivo      = Column(Text, nullable=True)       # causa da indisponibilidade
    observacoes = Column(Text, nullable=True)

    registrado_por_id = Column(Integer, ForeignKey("funcionarios.id", ondelete="SET NULL"), nullable=True)
    encerrado_por_id  = Column(Integer, ForeignKey("funcionarios.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    tenant         = relationship("Tenant")
    chamado        = relationship("Chamado", back_populates="glosas", foreign_keys=[chamado_id])
    filial         = relationship("Filial",  foreign_keys=[filial_id])
    registrado_por = relationship("Funcionario", foreign_keys=[registrado_por_id])
    encerrado_por  = relationship("Funcionario", foreign_keys=[encerrado_por_id])

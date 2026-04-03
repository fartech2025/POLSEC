"""
SLA — Acordo de Nível de Serviço por prioridade de chamado.

Cada tenant pode configurar prazos distintos por prioridade.
Os prazos são em horas úteis (contadas a partir de data_abertura).
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class SLAConfig(Base):
    """
    Configuração de SLA por tenant + prioridade.
    Garante unicidade (tenant_id, prioridade).

    prazo_resposta_horas  : horas para iniciar o atendimento (aberto → em_atendimento)
    prazo_resolucao_horas : horas para concluir o chamado
    """
    __tablename__ = "sla_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "prioridade", name="uq_sla_tenant_prioridade"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    prioridade = Column(String(20), nullable=False)          # baixa | media | alta | critica

    prazo_resposta_horas  = Column(Float, nullable=False)    # Ex: 4.0
    prazo_resolucao_horas = Column(Float, nullable=False)    # Ex: 24.0

    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")

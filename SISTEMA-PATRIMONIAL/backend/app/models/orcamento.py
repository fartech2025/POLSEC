import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Enum,
    ForeignKey, Text, Boolean,
)
from sqlalchemy.orm import relationship
from app.database import Base


class StatusOrcamento(str, enum.Enum):
    """
    Fluxo formal de aprovação:

        rascunho
            │
            ▼
        aguardando_aprovacao  ──► rejeitado
            │
            ▼
        aprovado
            │  (ou)
            ▼
        cancelado
    """
    rascunho = "rascunho"
    aguardando_aprovacao = "aguardando_aprovacao"
    aprovado = "aprovado"
    rejeitado = "rejeitado"
    cancelado = "cancelado"


class Orcamento(Base):
    """
    Orçamento de serviço vinculado a um chamado.
    O fluxo de aprovação é registrado em AprovacaoOrcamento.
    """
    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False)

    numero = Column(String(30), nullable=True)          # número sequencial do orçamento
    descricao_servico = Column(Text, nullable=False)
    valor_mao_obra = Column(Numeric(12, 2), nullable=True, default=0)
    valor_pecas = Column(Numeric(12, 2), nullable=True, default=0)
    valor_total = Column(Numeric(12, 2), nullable=False)

    status = Column(Enum(StatusOrcamento), default=StatusOrcamento.rascunho, nullable=False, index=True)

    # Criado por (funcionário)
    criado_por_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)

    # Prazo para aprovação (null = sem prazo)
    prazo_aprovacao = Column(DateTime, nullable=True)

    # Quem aprovou/rejeitou por último
    aprovado_por_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    data_aprovacao = Column(DateTime, nullable=True)

    # Arquivo PDF do orçamento no bucket
    bucket_path = Column(String(500), nullable=True)
    bucket_url = Column(String(1000), nullable=True)

    observacoes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relacionamentos ──────────────────────────────────────────────────────
    tenant = relationship("Tenant")
    chamado = relationship("Chamado", back_populates="orcamentos")
    criado_por = relationship("Funcionario", foreign_keys=[criado_por_id])
    aprovado_por = relationship("Funcionario", foreign_keys=[aprovado_por_id])
    historico = relationship(
        "AprovacaoOrcamento",
        back_populates="orcamento",
        order_by="AprovacaoOrcamento.created_at",
        cascade="all, delete-orphan",
    )


class AprovacaoOrcamento(Base):
    """
    Histórico imutável de cada transição de status do orçamento.
    Registra ator, ação, justificativa e timestamp — trilha de auditoria completa.
    """
    __tablename__ = "aprovacoes_orcamento"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)

    status_anterior = Column(Enum(StatusOrcamento), nullable=True)
    status_novo = Column(Enum(StatusOrcamento), nullable=False)
    ator_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)  # quem executou a ação
    justificativa = Column(Text, nullable=True)
    notificacoes_enviadas = Column(Boolean, default=False)    # True = e-mail disparado
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
    orcamento = relationship("Orcamento", back_populates="historico")
    ator = relationship("Funcionario")


class NotaFiscal(Base):
    """
    Nota fiscal vinculada a um chamado ou orçamento.
    O arquivo (PDF/XML) é armazenado no bucket Supabase Storage.
    """
    __tablename__ = "notas_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=True)

    numero_nf = Column(String(60), nullable=True)
    fornecedor = Column(String(200), nullable=True)
    valor = Column(Numeric(12, 2), nullable=True)
    data_emissao = Column(DateTime, nullable=True)

    bucket_path = Column(String(500), nullable=False)
    bucket_url = Column(String(1000), nullable=True)
    mime_type = Column(String(100), nullable=True)
    tamanho_kb = Column(Integer, nullable=True)

    registrado_por_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
    chamado = relationship("Chamado")
    orcamento = relationship("Orcamento")
    registrado_por = relationship("Funcionario")

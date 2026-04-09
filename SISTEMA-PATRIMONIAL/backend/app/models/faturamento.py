from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime,
    ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class FaturamentoHistorico(Base):
    """
    Registro fechado/imutável de faturamento por unidade e período.
    Pode originar de:
      - "sistema"     → fechamento manual do admin sobre dados dos chamados/orçamentos
      - "importacao"  → leitura de planilha Excel externa (legado / histórico)
    """
    __tablename__ = "faturamento_historico"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "filial_nome", "mes", "ano", "origem",
            name="uq_fat_hist_unidade_periodo",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # FK à filial — pode ser NULL se a unidade não existir ainda no cadastro
    filial_id = Column(Integer, ForeignKey("filiais.id"), nullable=True)
    # Nome snapshot: preservado mesmo que a filial seja renomeada/excluída
    filial_nome = Column(String(150), nullable=False)

    mes = Column(Integer, nullable=False)   # 1–12
    ano = Column(Integer, nullable=False)

    chamados_count = Column(Integer, default=0, nullable=False)
    valor_mao_obra = Column(Numeric(12, 2), default=0, nullable=False)
    valor_pecas    = Column(Numeric(12, 2), default=0, nullable=False)
    valor_total    = Column(Numeric(12, 2), nullable=False)

    observacoes     = Column(Text, nullable=True)
    # "sistema" | "importacao"
    origem          = Column(String(20), nullable=False, default="sistema")
    arquivo_origem  = Column(String(255), nullable=True)   # nome do xlsx importado

    fechado_por_id  = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    fechado_em      = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ── Relacionamentos ──────────────────────────────────────────────────────
    tenant      = relationship("Tenant")
    filial      = relationship("Filial")
    fechado_por = relationship("Funcionario")

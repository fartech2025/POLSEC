import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class StatusPatrimonio(str, enum.Enum):
    ativo = "ativo"
    manutencao = "manutencao"
    baixado = "baixado"
    extraviado = "extraviado"


class Patrimonio(Base):
    __tablename__ = "patrimonios"
    __table_args__ = (
        # Código único por tenant — evita duplicatas entre empresas diferentes
        UniqueConstraint("tenant_id", "codigo", name="uq_patrimonio_tenant_codigo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    codigo = Column(String(50), nullable=False, index=True)          # único por tenant (enforced via UNIQUE(tenant_id, codigo))
    descricao = Column(String(255), nullable=False)
    categoria = Column(String(100), nullable=False)
    setor = Column(String(100), nullable=False)
    localizacao = Column(String(150))
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_aquisicao = Column(DateTime, nullable=True)
    valor = Column(Numeric(12, 2), nullable=True)
    status = Column(Enum(StatusPatrimonio), default=StatusPatrimonio.ativo, nullable=False)
    observacoes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    responsavel = relationship("Usuario", back_populates="patrimonios")
    movimentacoes = relationship("Movimentacao", back_populates="patrimonio")

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.database import Base


class TipoMovimentacao(str, enum.Enum):
    transferencia_setor = "transferencia_setor"
    troca_responsavel = "troca_responsavel"
    mudanca_status = "mudanca_status"
    edicao_dados = "edicao_dados"


class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    patrimonio_id = Column(Integer, ForeignKey("patrimonios.id"), nullable=False)
    tipo = Column(Enum(TipoMovimentacao), nullable=False)
    descricao = Column(Text, nullable=True)
    dados_anteriores = Column(JSON, nullable=True)
    dados_novos = Column(JSON, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    patrimonio = relationship("Patrimonio", back_populates="movimentacoes")
    usuario = relationship("Usuario", back_populates="movimentacoes")

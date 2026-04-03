from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Filial(Base):
    """
    Filial / depósito da empresa (tenant).
    Usada para segregar estoque e equipes por localidade.
    """
    __tablename__ = "filiais"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    codigo = Column(String(30), nullable=True)       # código interno (opcional)
    endereco = Column(String(255), nullable=True)
    cidade = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(9), nullable=True)
    telefone = Column(String(20), nullable=True)
    responsavel_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)  # FK criada depois
    ativa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    responsavel = relationship("Funcionario", foreign_keys=[responsavel_id])
    estoques = relationship("EstoqueFilial", back_populates="filial")
    funcionarios = relationship(
        "Funcionario",
        back_populates="filial",
        foreign_keys="Funcionario.filial_id",
    )

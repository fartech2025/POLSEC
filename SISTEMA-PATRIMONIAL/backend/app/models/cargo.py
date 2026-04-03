from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Cargo(Base):
    """
    Cargo na hierarquia da empresa.

    nivel_hierarquico:
        1 = Diretor
        2 = Gerente
        3 = Coordenador
        4 = Supervisor
        5 = Técnico Sênior
        6 = Técnico
        7 = Auxiliar

    permissoes: JSON com módulos e ações liberadas, ex.:
        {
          "chamados":     ["criar", "ver", "editar", "cancelar", "aprovar"],
          "orcamentos":   ["criar", "ver", "aprovar", "rejeitar"],
          "pecas":        ["ver", "criar", "editar"],
          "patrimonios":  ["ver", "criar", "editar", "baixar"],
          "funcionarios": ["ver", "criar", "editar"],
          "financeiro":   ["ver", "aprovar"]
        }
    """
    __tablename__ = "cargos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    nivel_hierarquico = Column(Integer, nullable=False)  # 1 (mais alto) → 7 (mais baixo)
    descricao = Column(Text, nullable=True)
    permissoes = Column(JSON, nullable=False, default=dict)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    funcionarios = relationship("Funcionario", back_populates="cargo")

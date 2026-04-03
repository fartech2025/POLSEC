import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PerfilUsuario(str, enum.Enum):
    administrador = "administrador"
    operador = "operador"
    visualizador = "visualizador"


class Usuario(Base):
    """
    Usuário do sistema. O campo `supabase_uid` vincula ao Supabase Auth.
    O campo `tenant_id` isola dados por empresa.
    """
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    supabase_uid = Column(String(36), unique=True, index=True, nullable=False)  # UUID do Supabase Auth
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False)
    perfil = Column(Enum(PerfilUsuario), default=PerfilUsuario.operador, nullable=False)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    patrimonios = relationship("Patrimonio", back_populates="responsavel")
    movimentacoes = relationship("Movimentacao", back_populates="usuario")
    audit_logs = relationship("AuditLog", back_populates="usuario")

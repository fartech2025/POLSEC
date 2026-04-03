from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from app.database import Base


class Tenant(Base):
    """
    Representa uma empresa/organização no sistema multitenant.
    O tenant_id é gerado pelo Supabase Auth (UUID do usuário que criou a conta).
    """
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True)          # UUID — gerado pelo Supabase
    slug = Column(String(100), unique=True, nullable=False)  # ex: "emtel", "polsec"
    nome = Column(String(200), nullable=False)
    email_admin = Column(String(150), nullable=False)
    plano = Column(String(50), default="basico")        # basico | profissional | enterprise
    ativo = Column(Boolean, default=True)
    logo_url = Column(String(500), nullable=True)
    configuracoes = Column(Text, nullable=True)         # JSON com configs do tenant
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

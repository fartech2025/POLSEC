from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class GastoDiesel(Base):
    __tablename__ = "gastos_diesel"

    id          = Column(Integer, primary_key=True, index=True)
    tenant_id   = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    data        = Column(DateTime, nullable=False)
    numero_nota = Column(Integer, nullable=True, index=True)  # número do registro na planilha
    descricao   = Column(String(300), nullable=False)         # ex: "Abastecimento Óleo diesel - Limeira"
    local       = Column(String(150), nullable=True)          # ex: "Limeira" (extraído da descricao)
    tecnico     = Column(String(150), nullable=True)          # motorista / responsável
    litros      = Column(Numeric(10, 3), nullable=True)
    valor_litro = Column(Numeric(8, 3), nullable=True)
    valor_total = Column(Numeric(12, 2), nullable=False)
    observacoes = Column(Text, nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")

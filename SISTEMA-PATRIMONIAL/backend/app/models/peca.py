import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Enum,
    ForeignKey, Text, Boolean, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class UnidadePeca(str, enum.Enum):
    unidade = "unidade"
    par = "par"
    metro = "metro"
    litro = "litro"
    kg = "kg"
    caixa = "caixa"
    rolo = "rolo"


class Peca(Base):
    """
    Catálogo de peças / insumos utilizados nos chamados.
    SKU único por tenant.
    """
    __tablename__ = "pecas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_peca_tenant_sku"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    sku = Column(String(60), nullable=False)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    categoria = Column(String(100), nullable=True)
    marca = Column(String(100), nullable=True)
    unidade = Column(Enum(UnidadePeca), default=UnidadePeca.unidade, nullable=False)
    valor_unitario = Column(Numeric(12, 2), nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    estoque_geral = relationship("EstoqueGeral", back_populates="peca", uselist=False)
    estoques_filial = relationship("EstoqueFilial", back_populates="peca")
    pecas_chamado = relationship("PecaChamado", back_populates="peca")


class EstoqueGeral(Base):
    """
    Estoque consolidado por empresa (tenant).
    Serve como visão macro antes de movimentar para filiais.
    """
    __tablename__ = "estoque_geral"
    __table_args__ = (
        UniqueConstraint("tenant_id", "peca_id", name="uq_estoque_geral_tenant_peca"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id"), nullable=False)

    qtd_atual = Column(Numeric(12, 3), nullable=False, default=0)
    qtd_minima = Column(Numeric(12, 3), nullable=False, default=0)   # alerta de reposição
    qtd_maxima = Column(Numeric(12, 3), nullable=True)
    custo_medio = Column(Numeric(12, 4), nullable=True)              # preço médio ponderado

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    peca = relationship("Peca", back_populates="estoque_geral")


class EstoqueFilial(Base):
    """
    Estoque segregado por filial/depósito.
    Permite rastrear onde cada peça está fisicamente.
    """
    __tablename__ = "estoque_filial"
    __table_args__ = (
        UniqueConstraint("filial_id", "peca_id", name="uq_estoque_filial_peca"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    filial_id = Column(Integer, ForeignKey("filiais.id"), nullable=False)
    peca_id = Column(Integer, ForeignKey("pecas.id"), nullable=False)

    qtd_atual = Column(Numeric(12, 3), nullable=False, default=0)
    qtd_minima = Column(Numeric(12, 3), nullable=False, default=0)
    qtd_maxima = Column(Numeric(12, 3), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")
    filial = relationship("Filial", back_populates="estoques")
    peca = relationship("Peca", back_populates="estoques_filial")


class PecaChamado(Base):
    """
    Peças utilizadas / reservadas em um chamado.
    Quando confirmado, desconta do EstoqueFilial (ou EstoqueGeral).
    """
    __tablename__ = "pecas_chamado"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False)
    peca_id = Column(Integer, ForeignKey("pecas.id"), nullable=False)
    filial_origem_id = Column(Integer, ForeignKey("filiais.id"), nullable=True)

    quantidade = Column(Numeric(12, 3), nullable=False)
    valor_unitario = Column(Numeric(12, 2), nullable=True)  # snapshot do preço na data
    confirmado = Column(Boolean, default=False)              # True = débito de estoque efetivado
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
    chamado = relationship("Chamado")
    peca = relationship("Peca", back_populates="pecas_chamado")
    filial_origem = relationship("Filial")

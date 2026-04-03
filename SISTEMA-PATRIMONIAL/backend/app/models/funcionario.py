from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from app.database import Base


class Funcionario(Base):
    """
    Funcionário da empresa.  Entidade independente do Usuario (login é opcional).

    - usuario_id nullable: funcionário pode existir sem acesso ao sistema.
    - gestor_id auto-referencial: permite montar a árvore hierárquica.
    - filial_id: lotação principal.
    - cargo_id: determina nível hierárquico e permissões RBAC.
    """
    __tablename__ = "funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Identificação
    matricula = Column(String(30), nullable=False)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=True)
    telefone = Column(String(20), nullable=True)
    cpf = Column(String(14), nullable=True)

    # Estrutura organizacional
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)
    filial_id = Column(Integer, ForeignKey("filiais.id"), nullable=True)
    gestor_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)  # self-ref

    # Datas
    data_admissao = Column(Date, nullable=True)
    data_demissao = Column(Date, nullable=True)

    # Vínculo com acesso ao sistema (opcional)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, unique=True)

    ativo = Column(Boolean, default=True)
    observacoes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relacionamentos ──────────────────────────────────────────────────────
    tenant = relationship("Tenant")
    cargo = relationship("Cargo", back_populates="funcionarios")
    filial = relationship("Filial", back_populates="funcionarios", foreign_keys=[filial_id])
    gestor = relationship("Funcionario", remote_side=[id], foreign_keys=[gestor_id])
    subordinados = relationship(
        "Funcionario",
        back_populates="gestor",
        foreign_keys=[gestor_id],
    )
    usuario = relationship("Usuario", foreign_keys=[usuario_id])

    # Chamados onde este funcionário é técnico responsável
    chamados_como_tecnico = relationship(
        "Chamado",
        back_populates="tecnico",
        foreign_keys="Chamado.tecnico_id",
    )

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class TipoChamado(str, enum.Enum):
    preventiva = "preventiva"
    corretiva  = "corretiva"


class PrioridadeChamado(str, enum.Enum):
    baixa = "baixa"
    media = "media"
    alta = "alta"
    critica = "critica"


class StatusChamado(str, enum.Enum):
    """
    Máquina de estados do chamado:

        aberto
          │
          ▼
       em_atendimento ──► aguardando_peca
          │                      │
          │◄─────────────────────┘
          │
          ▼
       aguardando_aprovacao ──► rejeitado
          │
          ▼
       concluido
          │  (ou a qualquer momento)
          ▼
       cancelado
    """
    aberto = "aberto"
    em_atendimento = "em_atendimento"
    aguardando_peca = "aguardando_peca"
    aguardando_aprovacao = "aguardando_aprovacao"
    concluido = "concluido"
    cancelado = "cancelado"
    rejeitado = "rejeitado"


class Chamado(Base):
    __tablename__ = "chamados"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    # Equipamento / patrimônio alvo
    patrimonio_id = Column(Integer, ForeignKey("patrimonios.id"), nullable=False)

    # Quem abriu e quem atende
    solicitante_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    filial_id = Column(Integer, ForeignKey("filiais.id"), nullable=True)

    # Conteúdo
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=False)
    diagnostico = Column(Text, nullable=True)
    solucao_aplicada = Column(Text, nullable=True)

    # Estado
    status = Column(Enum(StatusChamado), default=StatusChamado.aberto, nullable=False, index=True)
    prioridade = Column(Enum(PrioridadeChamado), default=PrioridadeChamado.media, nullable=False)

    # Campos SLA / planilha de chamados
    numero_chamado        = Column(Integer, nullable=True, index=True)  # seq. visível
    tipo_chamado          = Column(Enum(TipoChamado), nullable=True)    # preventiva | corretiva
    data_chegada_tecnico  = Column(DateTime, nullable=True)             # chegada on-site
    justificativa_atraso  = Column(Text, nullable=True)                 # quando SLA violado
    codigo_unidade        = Column(String(10), nullable=True)           # ex: "3.08"

    # Datas de controle
    data_abertura = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_inicio_atendimento = Column(DateTime, nullable=True)
    data_previsao = Column(DateTime, nullable=True)
    data_conclusao = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relacionamentos ──────────────────────────────────────────────────────
    tenant = relationship("Tenant")
    patrimonio = relationship("Patrimonio")
    solicitante = relationship("Funcionario", foreign_keys=[solicitante_id])
    tecnico = relationship("Funcionario", back_populates="chamados_como_tecnico", foreign_keys=[tecnico_id])
    filial = relationship("Filial")
    anexos = relationship("AnexoChamado", back_populates="chamado", cascade="all, delete-orphan")
    orcamentos = relationship("Orcamento", back_populates="chamado")
    glosas = relationship("GlosaChamado", back_populates="chamado", foreign_keys="GlosaChamado.chamado_id")


class TipoAnexo(str, enum.Enum):
    foto = "foto"
    orcamento_pdf = "orcamento_pdf"
    nota_fiscal = "nota_fiscal"
    laudo = "laudo"
    outro = "outro"


class AnexoChamado(Base):
    """
    Arquivo armazenado no bucket Supabase Storage.
    Caminho: polsec-anexos/{tenant_slug}/chamados/{chamado_id}/{tipo}/{filename}
    Fotos são comprimidas (WebP, max 1920px) antes do upload.
    """
    __tablename__ = "anexos_chamado"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False, index=True)

    tipo = Column(Enum(TipoAnexo), nullable=False)
    nome_original = Column(String(255), nullable=False)
    bucket_path = Column(String(500), nullable=False)   # caminho dentro do bucket
    bucket_url = Column(String(1000), nullable=True)    # URL pública ou signed (gerada on-demand)
    mime_type = Column(String(100), nullable=True)
    tamanho_kb = Column(Integer, nullable=True)         # tamanho após compressão

    enviado_por_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
    chamado = relationship("Chamado", back_populates="anexos")
    enviado_por = relationship("Funcionario")

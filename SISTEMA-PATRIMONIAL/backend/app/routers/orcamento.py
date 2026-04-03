from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

from app.database import get_db
from app.models.orcamento import (
    Orcamento, AprovacaoOrcamento, NotaFiscal, StatusOrcamento
)
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services import storage_service

router = APIRouter()


# ── Schemas inline ────────────────────────────────────────────────────────────

class OrcamentoIn(BaseModel):
    chamado_id: int
    descricao_servico: str
    valor_mao_obra: Optional[Decimal] = Decimal("0")
    valor_pecas: Optional[Decimal] = Decimal("0")
    valor_total: Decimal
    criado_por_id: Optional[int] = None
    prazo_aprovacao: Optional[datetime] = None
    observacoes: Optional[str] = None


class OrcamentoOut(BaseModel):
    id: int
    chamado_id: int
    numero: Optional[str]
    descricao_servico: str
    valor_mao_obra: Optional[Decimal]
    valor_pecas: Optional[Decimal]
    valor_total: Decimal
    status: StatusOrcamento
    criado_por_id: Optional[int]
    aprovado_por_id: Optional[int]
    prazo_aprovacao: Optional[datetime]
    data_aprovacao: Optional[datetime]
    bucket_url: Optional[str]
    observacoes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AprovacaoIn(BaseModel):
    justificativa: Optional[str] = None
    ator_id: Optional[int] = None


class AprovacaoHistoricoOut(BaseModel):
    id: int
    status_anterior: Optional[StatusOrcamento]
    status_novo: StatusOrcamento
    ator_id: Optional[int]
    justificativa: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotaFiscalOut(BaseModel):
    id: int
    numero_nf: Optional[str]
    fornecedor: Optional[str]
    valor: Optional[Decimal]
    data_emissao: Optional[datetime]
    bucket_url: Optional[str]
    mime_type: Optional[str]
    tamanho_kb: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Orçamentos CRUD ───────────────────────────────────────────────────────────

@router.get("/", response_model=list[OrcamentoOut])
def listar_orcamentos(
    chamado_id: Optional[int] = None,
    status_filtro: Optional[StatusOrcamento] = None,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    q = db.query(Orcamento).filter(Orcamento.tenant_id == tenant.id)
    if chamado_id:
        q = q.filter(Orcamento.chamado_id == chamado_id)
    if status_filtro:
        q = q.filter(Orcamento.status == status_filtro)
    return q.order_by(Orcamento.created_at.desc()).all()


@router.post("/", response_model=OrcamentoOut, status_code=status.HTTP_201_CREATED)
def criar_orcamento(
    dados: OrcamentoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    orc = Orcamento(tenant_id=tenant.id, **dados.model_dump())
    db.add(orc)
    db.flush()
    # Registra histórico de criação
    _registrar_historico(db, orc, None, StatusOrcamento.rascunho, dados.criado_por_id)
    db.commit()
    db.refresh(orc)
    return orc


@router.get("/{orcamento_id}", response_model=OrcamentoOut)
def detalhe_orcamento(
    orcamento_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    return orc


# ── Fluxo de aprovação formal ────────────────────────────────────────────────

@router.post("/{orcamento_id}/submeter", response_model=OrcamentoOut)
def submeter_para_aprovacao(
    orcamento_id: int,
    dados: AprovacaoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Move de 'rascunho' para 'aguardando_aprovacao'."""
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    _transicionar_orcamento(db, orc, StatusOrcamento.aguardando_aprovacao, dados)
    db.commit()
    db.refresh(orc)
    return orc


@router.post("/{orcamento_id}/aprovar", response_model=OrcamentoOut)
def aprovar_orcamento(
    orcamento_id: int,
    dados: AprovacaoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Aprova o orçamento (requer estar em 'aguardando_aprovacao')."""
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    _transicionar_orcamento(db, orc, StatusOrcamento.aprovado, dados)
    # Atualiza aprovado_por e data_aprovacao na mesma transação (atômico)
    orc.aprovado_por_id = dados.ator_id
    orc.data_aprovacao = datetime.utcnow()
    db.commit()
    db.refresh(orc)
    return orc


@router.post("/{orcamento_id}/rejeitar", response_model=OrcamentoOut)
def rejeitar_orcamento(
    orcamento_id: int,
    dados: AprovacaoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Rejeita o orçamento com justificativa obrigatória."""
    if not dados.justificativa:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Justificativa obrigatória para rejeição do orçamento.",
        )
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    _transicionar_orcamento(db, orc, StatusOrcamento.rejeitado, dados)
    db.commit()
    db.refresh(orc)
    return orc


@router.post("/{orcamento_id}/cancelar", response_model=OrcamentoOut)
def cancelar_orcamento(
    orcamento_id: int,
    dados: AprovacaoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    _transicionar_orcamento(db, orc, StatusOrcamento.cancelado, dados)
    db.commit()
    db.refresh(orc)
    return orc


@router.get("/{orcamento_id}/historico", response_model=list[AprovacaoHistoricoOut])
def historico_aprovacao(
    orcamento_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Retorna a trilha de auditoria completa do orçamento."""
    _buscar_ou_404(db, orcamento_id, tenant.id)
    return (
        db.query(AprovacaoOrcamento)
        .filter(AprovacaoOrcamento.orcamento_id == orcamento_id)
        .order_by(AprovacaoOrcamento.created_at)
        .all()
    )


# ── Upload de PDF do orçamento ────────────────────────────────────────────────

@router.post("/{orcamento_id}/pdf", response_model=OrcamentoOut)
async def anexar_pdf_orcamento(
    orcamento_id: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    dados = await arquivo.read(_MAX_UPLOAD_BYTES + 1)
    if len(dados) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo excede o limite de 10 MB.")
    path = storage_service.montar_path_orcamento(tenant.slug, orc.chamado_id, arquivo.filename)
    bucket_path, _, _ = storage_service.processar_e_enviar_documento(dados, path)
    orc.bucket_path = bucket_path
    orc.bucket_url = storage_service.gerar_url_publica(bucket_path)
    db.commit()
    db.refresh(orc)
    return orc


# ── Notas fiscais ─────────────────────────────────────────────────────────────

@router.post("/{orcamento_id}/nota-fiscal", response_model=NotaFiscalOut, status_code=status.HTTP_201_CREATED)
async def registrar_nota_fiscal(
    orcamento_id: int,
    numero_nf: Optional[str] = Form(None),
    fornecedor: Optional[str] = Form(None),
    valor: Optional[Decimal] = Form(None),
    data_emissao: Optional[datetime] = Form(None),
    registrado_por_id: Optional[int] = Form(None),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    orc = _buscar_ou_404(db, orcamento_id, tenant.id)
    dados = await arquivo.read(_MAX_UPLOAD_BYTES + 1)
    if len(dados) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Arquivo excede o limite de 10 MB.")
    path = storage_service.montar_path_nota_fiscal(tenant.slug, orc.chamado_id, arquivo.filename)
    bucket_path, mime_type, tamanho_kb = storage_service.processar_e_enviar_documento(dados, path)
    url = storage_service.gerar_url_publica(bucket_path)

    nf = NotaFiscal(
        tenant_id=tenant.id,
        chamado_id=orc.chamado_id,
        orcamento_id=orcamento_id,
        numero_nf=numero_nf,
        fornecedor=fornecedor,
        valor=valor,
        data_emissao=data_emissao,
        bucket_path=bucket_path,
        bucket_url=url,
        mime_type=mime_type,
        tamanho_kb=tamanho_kb,
        registrado_por_id=registrado_por_id,
    )
    db.add(nf)
    db.commit()
    db.refresh(nf)
    return nf


# ── Helpers privados ──────────────────────────────────────────────────────────

_TRANSICOES_ORCAMENTO: dict[StatusOrcamento, set[StatusOrcamento]] = {
    StatusOrcamento.rascunho: {StatusOrcamento.aguardando_aprovacao, StatusOrcamento.cancelado},
    StatusOrcamento.aguardando_aprovacao: {
        StatusOrcamento.aprovado, StatusOrcamento.rejeitado, StatusOrcamento.cancelado
    },
    StatusOrcamento.aprovado: set(),
    StatusOrcamento.rejeitado: set(),
    StatusOrcamento.cancelado: set(),
}


def _buscar_ou_404(db: Session, orcamento_id: int, tenant_id: str) -> Orcamento:
    orc = db.query(Orcamento).filter(
        Orcamento.id == orcamento_id, Orcamento.tenant_id == tenant_id
    ).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    return orc


def _transicionar_orcamento(
    db: Session, orc: Orcamento, novo_status: StatusOrcamento, dados: AprovacaoIn
) -> None:
    destinos = _TRANSICOES_ORCAMENTO.get(orc.status, set())
    if novo_status not in destinos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transição inválida para orçamento: '{orc.status}' → '{novo_status}'. "
                f"Permitidas: {[s.value for s in destinos] or 'nenhuma (estado terminal)'}."
            ),
        )
    _registrar_historico(db, orc, orc.status, novo_status, dados.ator_id, dados.justificativa)
    orc.status = novo_status
    # NÃO commita aqui — responsabilidade do caller para garantir atomicidade.


def _registrar_historico(
    db: Session,
    orc: Orcamento,
    status_anterior: Optional[StatusOrcamento],
    status_novo: StatusOrcamento,
    ator_id: Optional[int],
    justificativa: Optional[str] = None,
) -> None:
    entrada = AprovacaoOrcamento(
        tenant_id=orc.tenant_id,
        orcamento_id=orc.id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        ator_id=ator_id,
        justificativa=justificativa,
    )
    db.add(entrada)

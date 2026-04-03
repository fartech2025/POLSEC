from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.chamado import Chamado, AnexoChamado, StatusChamado, PrioridadeChamado, TipoAnexo
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.chamado_service import ChamadoService
from app.services import storage_service

router = APIRouter()


# ── Schemas inline ────────────────────────────────────────────────────────────

class ChamadoIn(BaseModel):
    patrimonio_id: int
    solicitante_id: int
    tecnico_id: Optional[int] = None
    filial_id: Optional[int] = None
    titulo: str
    descricao: str
    prioridade: PrioridadeChamado = PrioridadeChamado.media
    data_previsao: Optional[datetime] = None


class ChamadoOut(BaseModel):
    id: int
    patrimonio_id: int
    solicitante_id: int
    tecnico_id: Optional[int]
    filial_id: Optional[int]
    titulo: str
    descricao: str
    diagnostico: Optional[str]
    solucao_aplicada: Optional[str]
    status: StatusChamado
    prioridade: PrioridadeChamado
    data_abertura: datetime
    data_inicio_atendimento: Optional[datetime]
    data_previsao: Optional[datetime]
    data_conclusao: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TransicaoIn(BaseModel):
    novo_status: StatusChamado
    tecnico_id: Optional[int] = None


class AtualizacaoTecnicaIn(BaseModel):
    diagnostico: Optional[str] = None
    solucao_aplicada: Optional[str] = None


class AnexoOut(BaseModel):
    id: int
    tipo: TipoAnexo
    nome_original: str
    bucket_url: Optional[str]
    mime_type: Optional[str]
    tamanho_kb: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ChamadoOut])
def listar_chamados(
    status_filtro: Optional[StatusChamado] = None,
    tecnico_id: Optional[int] = None,
    patrimonio_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    svc = ChamadoService(db)
    return svc.listar(
        tenant_id=tenant.id,
        status_filtro=status_filtro,
        tecnico_id=tecnico_id,
        patrimonio_id=patrimonio_id,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=ChamadoOut, status_code=status.HTTP_201_CREATED)
def abrir_chamado(
    dados: ChamadoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    chamado = Chamado(tenant_id=tenant.id, **dados.model_dump())
    db.add(chamado)
    db.commit()
    db.refresh(chamado)
    return chamado


@router.get("/{chamado_id}", response_model=ChamadoOut)
def detalhe_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    return ChamadoService(db).buscar_ou_404(chamado_id, tenant.id)


@router.post("/{chamado_id}/transicao", response_model=ChamadoOut)
def transicionar_chamado(
    chamado_id: int,
    dados: TransicaoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Avança ou recua o status do chamado conforme a máquina de estados."""
    svc = ChamadoService(db)
    chamado = svc.buscar_ou_404(chamado_id, tenant.id)
    tecnico = None
    if dados.tecnico_id:
        from app.models.funcionario import Funcionario
        tecnico = db.query(Funcionario).filter(
            Funcionario.id == dados.tecnico_id, Funcionario.tenant_id == tenant.id
        ).first()
        if not tecnico:
            raise HTTPException(status_code=404, detail="Técnico não encontrado neste tenant.")
    return svc.transicionar(chamado, dados.novo_status, tecnico=tecnico)


@router.patch("/{chamado_id}/tecnico", response_model=ChamadoOut)
def atualizar_informacoes_tecnicas(
    chamado_id: int,
    dados: AtualizacaoTecnicaIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    chamado = ChamadoService(db).buscar_ou_404(chamado_id, tenant.id)
    if dados.diagnostico is not None:
        chamado.diagnostico = dados.diagnostico
    if dados.solucao_aplicada is not None:
        chamado.solucao_aplicada = dados.solucao_aplicada
    db.commit()
    db.refresh(chamado)
    return chamado


# ── Anexos ────────────────────────────────────────────────────────────────────

@router.get("/{chamado_id}/anexos", response_model=list[AnexoOut])
def listar_anexos(
    chamado_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    ChamadoService(db).buscar_ou_404(chamado_id, tenant.id)
    return db.query(AnexoChamado).filter(
        AnexoChamado.chamado_id == chamado_id,
        AnexoChamado.tenant_id == tenant.id,
    ).all()


@router.post("/{chamado_id}/anexos", response_model=AnexoOut, status_code=status.HTTP_201_CREATED)
async def enviar_anexo(
    chamado_id: int,
    tipo: TipoAnexo = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """
    Faz upload de arquivo para o chamado.
    Fotos são automaticamente comprimidas (WebP, max 1920px).
    Documentos (PDF, XML) são enviados sem alteração.
    Limite: 10 MB por arquivo.
    """
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
    ChamadoService(db).buscar_ou_404(chamado_id, tenant.id)
    dados = await arquivo.read(_MAX_UPLOAD_BYTES + 1)
    if len(dados) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo excede o limite de 10 MB.",
        )

    if tipo == TipoAnexo.foto:
        nome_base = arquivo.filename.rsplit(".", 1)[0]
        bucket_path, mime_final, tamanho_kb = storage_service.processar_e_enviar_foto(
            dados, tenant.slug, chamado_id, nome_base
        )
    else:
        # Mapeia tipo para subpasta correta no bucket
        _path_builders = {
            TipoAnexo.orcamento_pdf: storage_service.montar_path_orcamento,
            TipoAnexo.nota_fiscal:   storage_service.montar_path_nota_fiscal,
            TipoAnexo.laudo:         storage_service.montar_path_laudo,
            TipoAnexo.outro:         storage_service.montar_path_outro,
        }
        builder = _path_builders.get(tipo, storage_service.montar_path_outro)
        bucket_path_raw = builder(tenant.slug, chamado_id, arquivo.filename)
        bucket_path, mime_final, tamanho_kb = storage_service.processar_e_enviar_documento(
            dados, bucket_path_raw
        )

    url = storage_service.gerar_url_publica(bucket_path)
    anexo = AnexoChamado(
        tenant_id=tenant.id,
        chamado_id=chamado_id,
        tipo=tipo,
        nome_original=arquivo.filename,
        bucket_path=bucket_path,
        bucket_url=url,
        mime_type=mime_final,
        tamanho_kb=tamanho_kb,
    )
    db.add(anexo)
    db.commit()
    db.refresh(anexo)
    return anexo


@router.delete("/{chamado_id}/anexos/{anexo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_anexo(
    chamado_id: int,
    anexo_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    anexo = db.query(AnexoChamado).filter(
        AnexoChamado.id == anexo_id,
        AnexoChamado.chamado_id == chamado_id,
        AnexoChamado.tenant_id == tenant.id,
    ).first()
    if not anexo:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    storage_service.remover_arquivo(anexo.bucket_path)
    db.delete(anexo)
    db.commit()

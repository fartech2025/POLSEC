from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.peca import Peca, EstoqueGeral, EstoqueFilial, PecaChamado, UnidadePeca
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PecaIn(BaseModel):
    sku: str
    nome: str
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    marca: Optional[str] = None
    unidade: UnidadePeca = UnidadePeca.unidade
    valor_unitario: Optional[Decimal] = None
    ativo: bool = True


class PecaOut(BaseModel):
    id: int
    sku: str
    nome: str
    descricao: Optional[str]
    categoria: Optional[str]
    marca: Optional[str]
    unidade: UnidadePeca
    valor_unitario: Optional[Decimal]
    ativo: bool

    class Config:
        from_attributes = True


class EstoqueGeralOut(BaseModel):
    id: int
    peca_id: int
    qtd_atual: Decimal
    qtd_minima: Decimal
    qtd_maxima: Optional[Decimal]
    custo_medio: Optional[Decimal]

    class Config:
        from_attributes = True


class EstoqueFilialOut(BaseModel):
    id: int
    filial_id: int
    peca_id: int
    qtd_atual: Decimal
    qtd_minima: Decimal
    qtd_maxima: Optional[Decimal]

    class Config:
        from_attributes = True


class AjusteEstoqueIn(BaseModel):
    qtd_atual: Decimal
    qtd_minima: Optional[Decimal] = None
    qtd_maxima: Optional[Decimal] = None
    custo_medio: Optional[Decimal] = None  # só EstoqueGeral


# ── Peças CRUD ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[PecaOut])
def listar_pecas(
    busca: Optional[str] = None,
    categoria: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    q = db.query(Peca).filter(Peca.tenant_id == tenant.id, Peca.ativo.is_(True))
    if busca:
        q = q.filter(Peca.nome.ilike(f"%{busca}%") | Peca.sku.ilike(f"%{busca}%"))
    if categoria:
        q = q.filter(Peca.categoria == categoria)
    return q.order_by(Peca.nome).all()


@router.post("/", response_model=PecaOut, status_code=status.HTTP_201_CREATED)
def criar_peca(
    dados: PecaIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    peca = Peca(tenant_id=tenant.id, **dados.model_dump())
    db.add(peca)
    db.commit()
    db.refresh(peca)
    return peca


@router.get("/{peca_id}", response_model=PecaOut)
def detalhe_peca(
    peca_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    peca = db.query(Peca).filter(Peca.id == peca_id, Peca.tenant_id == tenant.id).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    return peca


@router.put("/{peca_id}", response_model=PecaOut)
def atualizar_peca(
    peca_id: int,
    dados: PecaIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    peca = db.query(Peca).filter(Peca.id == peca_id, Peca.tenant_id == tenant.id).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    for campo, valor in dados.model_dump().items():
        setattr(peca, campo, valor)
    db.commit()
    db.refresh(peca)
    return peca


# ── Estoque Geral ─────────────────────────────────────────────────────────────

@router.get("/{peca_id}/estoque/geral", response_model=EstoqueGeralOut)
def estoque_geral(
    peca_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    eg = db.query(EstoqueGeral).filter(
        EstoqueGeral.peca_id == peca_id, EstoqueGeral.tenant_id == tenant.id
    ).first()
    if not eg:
        raise HTTPException(status_code=404, detail="Estoque geral não encontrado para esta peça.")
    return eg


@router.put("/{peca_id}/estoque/geral", response_model=EstoqueGeralOut)
def ajustar_estoque_geral(
    peca_id: int,
    dados: AjusteEstoqueIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    eg = db.query(EstoqueGeral).filter(
        EstoqueGeral.peca_id == peca_id, EstoqueGeral.tenant_id == tenant.id
    ).first()
    if not eg:
        eg = EstoqueGeral(tenant_id=tenant.id, peca_id=peca_id)
        db.add(eg)
    eg.qtd_atual = dados.qtd_atual
    if dados.qtd_minima is not None:
        eg.qtd_minima = dados.qtd_minima
    if dados.qtd_maxima is not None:
        eg.qtd_maxima = dados.qtd_maxima
    if dados.custo_medio is not None:
        eg.custo_medio = dados.custo_medio
    db.commit()
    db.refresh(eg)
    return eg


# ── Estoque por Filial ────────────────────────────────────────────────────────

@router.get("/{peca_id}/estoque/filiais", response_model=list[EstoqueFilialOut])
def estoque_por_filial(
    peca_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    return db.query(EstoqueFilial).filter(
        EstoqueFilial.peca_id == peca_id, EstoqueFilial.tenant_id == tenant.id
    ).all()


@router.put("/{peca_id}/estoque/filiais/{filial_id}", response_model=EstoqueFilialOut)
def ajustar_estoque_filial(
    peca_id: int,
    filial_id: int,
    dados: AjusteEstoqueIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    ef = db.query(EstoqueFilial).filter(
        EstoqueFilial.peca_id == peca_id,
        EstoqueFilial.filial_id == filial_id,
        EstoqueFilial.tenant_id == tenant.id,
    ).first()
    if not ef:
        ef = EstoqueFilial(tenant_id=tenant.id, filial_id=filial_id, peca_id=peca_id)
        db.add(ef)
    ef.qtd_atual = dados.qtd_atual
    if dados.qtd_minima is not None:
        ef.qtd_minima = dados.qtd_minima
    if dados.qtd_maxima is not None:
        ef.qtd_maxima = dados.qtd_maxima
    db.commit()
    db.refresh(ef)
    return ef

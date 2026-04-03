from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.filial import Filial
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()


# ── Schemas inline ────────────────────────────────────────────────────────────

class FilialIn(BaseModel):
    nome: str
    codigo: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    responsavel_id: Optional[int] = None
    ativa: bool = True


class FilialOut(BaseModel):
    id: int
    nome: str
    codigo: Optional[str]
    endereco: Optional[str]
    cidade: Optional[str]
    estado: Optional[str]
    cep: Optional[str]
    telefone: Optional[str]
    responsavel_id: Optional[int]
    ativa: bool

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[FilialOut])
def listar_filiais(
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    return db.query(Filial).filter(Filial.tenant_id == tenant.id).order_by(Filial.nome).all()


@router.post("/", response_model=FilialOut, status_code=status.HTTP_201_CREATED)
def criar_filial(
    dados: FilialIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    filial = Filial(tenant_id=tenant.id, **dados.model_dump())
    db.add(filial)
    db.commit()
    db.refresh(filial)
    return filial


@router.get("/{filial_id}", response_model=FilialOut)
def detalhe_filial(
    filial_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    filial = db.query(Filial).filter(Filial.id == filial_id, Filial.tenant_id == tenant.id).first()
    if not filial:
        raise HTTPException(status_code=404, detail="Filial não encontrada.")
    return filial


@router.put("/{filial_id}", response_model=FilialOut)
def atualizar_filial(
    filial_id: int,
    dados: FilialIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    filial = db.query(Filial).filter(Filial.id == filial_id, Filial.tenant_id == tenant.id).first()
    if not filial:
        raise HTTPException(status_code=404, detail="Filial não encontrada.")
    for campo, valor in dados.model_dump().items():
        setattr(filial, campo, valor)
    db.commit()
    db.refresh(filial)
    return filial


@router.delete("/{filial_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_filial(
    filial_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    filial = db.query(Filial).filter(Filial.id == filial_id, Filial.tenant_id == tenant.id).first()
    if not filial:
        raise HTTPException(status_code=404, detail="Filial não encontrada.")
    try:
        db.delete(filial)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível remover: existem funcionários ou estoques vinculados a esta filial.",
        )

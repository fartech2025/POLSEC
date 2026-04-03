from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cargo import Cargo
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()


# ── Schemas inline ────────────────────────────────────────────────────────────

class CargoIn(BaseModel):
    nome: str
    nivel_hierarquico: int
    descricao: Optional[str] = None
    permissoes: dict = {}
    ativo: bool = True


class CargoOut(BaseModel):
    id: int
    nome: str
    nivel_hierarquico: int
    descricao: Optional[str]
    permissoes: dict
    ativo: bool

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[CargoOut])
def listar_cargos(
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    return (
        db.query(Cargo)
        .filter(Cargo.tenant_id == tenant.id)
        .order_by(Cargo.nivel_hierarquico)
        .all()
    )


@router.post("/", response_model=CargoOut, status_code=status.HTTP_201_CREATED)
def criar_cargo(
    dados: CargoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    cargo = Cargo(tenant_id=tenant.id, **dados.model_dump())
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return cargo


@router.get("/{cargo_id}", response_model=CargoOut)
def detalhe_cargo(
    cargo_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id, Cargo.tenant_id == tenant.id).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    return cargo


@router.put("/{cargo_id}", response_model=CargoOut)
def atualizar_cargo(
    cargo_id: int,
    dados: CargoIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id, Cargo.tenant_id == tenant.id).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    for campo, valor in dados.model_dump().items():
        setattr(cargo, campo, valor)
    db.commit()
    db.refresh(cargo)
    return cargo


@router.delete("/{cargo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_cargo(
    cargo_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id, Cargo.tenant_id == tenant.id).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    db.delete(cargo)
    db.commit()

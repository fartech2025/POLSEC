from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.funcionario import Funcionario
from app.services.auth_service import get_tenant_atual, get_usuario_logado

router = APIRouter()


# ── Schemas inline ────────────────────────────────────────────────────────────

class FuncionarioIn(BaseModel):
    matricula: str
    nome: str
    email: Optional[str] = None
    telefone: Optional[str] = None
    cpf: Optional[str] = None
    cargo_id: int
    filial_id: Optional[int] = None
    gestor_id: Optional[int] = None
    data_admissao: Optional[date] = None
    data_demissao: Optional[date] = None
    usuario_id: Optional[int] = None
    ativo: bool = True
    observacoes: Optional[str] = None


class CargoResumido(BaseModel):
    id: int
    nome: str
    nivel_hierarquico: int

    class Config:
        from_attributes = True


class FuncionarioOut(BaseModel):
    id: int
    matricula: str
    nome: str
    email: Optional[str]
    telefone: Optional[str]
    cargo_id: int
    cargo: Optional[CargoResumido]
    filial_id: Optional[int]
    gestor_id: Optional[int]
    usuario_id: Optional[int]
    ativo: bool
    data_admissao: Optional[date]

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[FuncionarioOut])
def listar_funcionarios(
    ativo: Optional[bool] = None,
    cargo_id: Optional[int] = None,
    filial_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    q = (
        db.query(Funcionario)
        .options(joinedload(Funcionario.cargo))
        .filter(Funcionario.tenant_id == tenant.id)
    )
    if ativo is not None:
        q = q.filter(Funcionario.ativo == ativo)
    if cargo_id:
        q = q.filter(Funcionario.cargo_id == cargo_id)
    if filial_id:
        q = q.filter(Funcionario.filial_id == filial_id)
    return q.order_by(Funcionario.nome).all()


@router.post("/", response_model=FuncionarioOut, status_code=status.HTTP_201_CREATED)
def criar_funcionario(
    dados: FuncionarioIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    funcionario = Funcionario(tenant_id=tenant.id, **dados.model_dump())
    db.add(funcionario)
    db.commit()
    db.refresh(funcionario)
    return funcionario


@router.get("/{funcionario_id}", response_model=FuncionarioOut)
def detalhe_funcionario(
    funcionario_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    func = (
        db.query(Funcionario)
        .options(joinedload(Funcionario.cargo))
        .filter(Funcionario.id == funcionario_id, Funcionario.tenant_id == tenant.id)
        .first()
    )
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return func


@router.put("/{funcionario_id}", response_model=FuncionarioOut)
def atualizar_funcionario(
    funcionario_id: int,
    dados: FuncionarioIn,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    func = db.query(Funcionario).filter(
        Funcionario.id == funcionario_id, Funcionario.tenant_id == tenant.id
    ).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    for campo, valor in dados.model_dump().items():
        setattr(func, campo, valor)
    db.commit()
    db.refresh(func)
    return func


@router.delete("/{funcionario_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_funcionario(
    funcionario_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Desativa o funcionário (soft delete) em vez de excluir."""
    func = db.query(Funcionario).filter(
        Funcionario.id == funcionario_id, Funcionario.tenant_id == tenant.id
    ).first()
    if not func:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    func.ativo = False
    db.commit()


@router.get("/{funcionario_id}/subordinados", response_model=list[FuncionarioOut])
def subordinados(
    funcionario_id: int,
    db: Session = Depends(get_db),
    tenant=Depends(get_tenant_atual),
    _usuario=Depends(get_usuario_logado),
):
    """Retorna a equipe direta (subordinados imediatos) de um funcionário."""
    return (
        db.query(Funcionario)
        .filter(
            Funcionario.gestor_id == funcionario_id,
            Funcionario.tenant_id == tenant.id,
            Funcionario.ativo.is_(True),
        )
        .order_by(Funcionario.nome)
        .all()
    )

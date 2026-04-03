from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.models.patrimonio import StatusPatrimonio


class PatrimonioBase(BaseModel):
    codigo: str
    descricao: str
    categoria: str
    setor: str
    localizacao: Optional[str] = None
    responsavel_id: Optional[int] = None
    data_aquisicao: Optional[datetime] = None
    valor: Optional[Decimal] = None
    status: StatusPatrimonio = StatusPatrimonio.ativo
    observacoes: Optional[str] = None


class PatrimonioCreate(PatrimonioBase):
    pass


class PatrimonioUpdate(BaseModel):
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    setor: Optional[str] = None
    localizacao: Optional[str] = None
    responsavel_id: Optional[int] = None
    data_aquisicao: Optional[datetime] = None
    valor: Optional[Decimal] = None
    status: Optional[StatusPatrimonio] = None
    observacoes: Optional[str] = None


class PatrimonioResponse(PatrimonioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

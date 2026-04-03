from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel

from app.models.movimentacao import TipoMovimentacao


class MovimentacaoCreate(BaseModel):
    patrimonio_id: int
    tipo: TipoMovimentacao
    descricao: Optional[str] = None
    dados_anteriores: Optional[Dict[str, Any]] = None
    dados_novos: Optional[Dict[str, Any]] = None


class MovimentacaoResponse(MovimentacaoCreate):
    id: int
    usuario_id: int
    created_at: datetime

    class Config:
        from_attributes = True

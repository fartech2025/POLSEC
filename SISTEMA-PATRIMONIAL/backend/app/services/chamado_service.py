"""
Chamado Service — lógica de negócio e máquina de estados para chamados de serviço.

Transições válidas:
    aberto             → em_atendimento, cancelado
    em_atendimento     → aguardando_peca, aguardando_aprovacao, concluido, cancelado
    aguardando_peca    → em_atendimento, cancelado
    aguardando_aprovacao → aprovado (→ concluido), rejeitado, cancelado
    concluido          → (terminal)
    cancelado          → (terminal)
    rejeitado          → (terminal)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.chamado import Chamado, StatusChamado
from app.models.funcionario import Funcionario

logger = logging.getLogger(__name__)

# ── Grafo de transições ───────────────────────────────────────────────────────
_TRANSICOES_VALIDAS: dict[StatusChamado, set[StatusChamado]] = {
    StatusChamado.aberto: {
        StatusChamado.em_atendimento,
        StatusChamado.cancelado,
    },
    StatusChamado.em_atendimento: {
        StatusChamado.aguardando_peca,
        StatusChamado.aguardando_aprovacao,
        StatusChamado.concluido,
        StatusChamado.cancelado,
    },
    StatusChamado.aguardando_peca: {
        StatusChamado.em_atendimento,
        StatusChamado.cancelado,
    },
    StatusChamado.aguardando_aprovacao: {
        StatusChamado.concluido,
        StatusChamado.rejeitado,
        StatusChamado.cancelado,
    },
    StatusChamado.concluido: set(),
    StatusChamado.cancelado: set(),
    StatusChamado.rejeitado: set(),
}


class ChamadoService:
    def __init__(self, db: Session):
        self.db = db

    # ── Máquina de estados ────────────────────────────────────────────────────

    def transicionar(
        self,
        chamado: Chamado,
        novo_status: StatusChamado,
        tecnico: Optional[Funcionario] = None,
    ) -> Chamado:
        """
        Aplica transição de status ao chamado.
        Levanta 422 se a transição não for permitida.
        Atualiza datas de controle automaticamente.
        """
        destinos = _TRANSICOES_VALIDAS.get(chamado.status, set())
        if novo_status not in destinos:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Transição inválida: '{chamado.status}' → '{novo_status}'. "
                    f"Transições permitidas: {[s.value for s in destinos] or 'nenhuma (estado terminal)'}."
                ),
            )

        status_anterior = chamado.status
        chamado.status = novo_status

        # Atualiza datas de controle
        if novo_status == StatusChamado.em_atendimento and chamado.data_inicio_atendimento is None:
            chamado.data_inicio_atendimento = datetime.utcnow()
            if tecnico:
                chamado.tecnico_id = tecnico.id

        if novo_status in (StatusChamado.concluido, StatusChamado.cancelado, StatusChamado.rejeitado):
            chamado.data_conclusao = datetime.utcnow()

        self.db.add(chamado)
        self.db.commit()
        self.db.refresh(chamado)

        logger.info(
            "Chamado #%d: %s → %s",
            chamado.id,
            status_anterior.value,
            novo_status.value,
        )
        return chamado

    # ── CRUD básico ───────────────────────────────────────────────────────────

    def buscar_ou_404(self, chamado_id: int, tenant_id: str) -> Chamado:
        chamado = (
            self.db.query(Chamado)
            .filter(Chamado.id == chamado_id, Chamado.tenant_id == tenant_id)
            .first()
        )
        if chamado is None:
            raise HTTPException(status_code=404, detail="Chamado não encontrado.")
        return chamado

    def listar(
        self,
        tenant_id: str,
        status_filtro: Optional[StatusChamado] = None,
        tecnico_id: Optional[int] = None,
        patrimonio_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Chamado]:
        q = self.db.query(Chamado).filter(Chamado.tenant_id == tenant_id)
        if status_filtro:
            q = q.filter(Chamado.status == status_filtro)
        if tecnico_id:
            q = q.filter(Chamado.tecnico_id == tecnico_id)
        if patrimonio_id:
            q = q.filter(Chamado.patrimonio_id == patrimonio_id)
        return q.order_by(Chamado.created_at.desc()).offset(offset).limit(limit).all()

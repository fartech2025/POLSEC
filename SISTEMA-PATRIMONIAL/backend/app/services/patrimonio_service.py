from math import ceil
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.movimentacao import Movimentacao, TipoMovimentacao
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.usuario import Usuario
from app.schemas.patrimonio import PatrimonioCreate, PatrimonioUpdate


class PatrimonioService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    PER_PAGE = 50

    def listar(
        self,
        busca: Optional[str] = None,
        setor: Optional[str] = None,
        status: Optional[str] = None,
        categoria: Optional[str] = None,
        page: int = 1,
    ) -> Tuple[List[Patrimonio], int, int]:
        """Retorna (itens, total, total_pages) com paginação."""
        query = self.db.query(Patrimonio).filter(
            Patrimonio.tenant_id == self.tenant_id
        )
        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                Patrimonio.codigo.ilike(termo)
                | Patrimonio.descricao.ilike(termo)
                | Patrimonio.localizacao.ilike(termo)
            )
        if setor:
            query = query.filter(Patrimonio.setor == setor)
        if status:
            query = query.filter(Patrimonio.status == StatusPatrimonio(status))
        if categoria:
            query = query.filter(Patrimonio.categoria == categoria)
        total = query.count()
        total_pages = max(1, ceil(total / self.PER_PAGE))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * self.PER_PAGE
        itens = query.order_by(Patrimonio.codigo).offset(offset).limit(self.PER_PAGE).all()
        return itens, total, total_pages

    def buscar_por_id(self, patrimonio_id: int) -> Optional[Patrimonio]:
        return (
            self.db.query(Patrimonio)
            .filter(
                Patrimonio.id == patrimonio_id,
                Patrimonio.tenant_id == self.tenant_id,
            )
            .first()
        )

    def listar_setores(self) -> List[str]:
        resultados = (
            self.db.query(Patrimonio.setor)
            .filter(Patrimonio.tenant_id == self.tenant_id, Patrimonio.setor.isnot(None))
            .distinct()
            .order_by(Patrimonio.setor)
            .all()
        )
        return [r[0] for r in resultados if r[0]]

    def listar_categorias(self) -> List[str]:
        resultados = (
            self.db.query(Patrimonio.categoria)
            .filter(Patrimonio.tenant_id == self.tenant_id, Patrimonio.categoria.isnot(None))
            .distinct()
            .order_by(Patrimonio.categoria)
            .all()
        )
        return [r[0] for r in resultados if r[0]]

    def contar_por_status(self) -> Dict[str, int]:
        from sqlalchemy import func
        rows = (
            self.db.query(Patrimonio.status, func.count(Patrimonio.id))
            .filter(Patrimonio.tenant_id == self.tenant_id)
            .group_by(Patrimonio.status)
            .all()
        )
        return {r[0].value if r[0] else "sem_status": r[1] for r in rows}

    def listar_responsaveis(self) -> List[Usuario]:
        return (
            self.db.query(Usuario)
            .filter(
                Usuario.tenant_id == self.tenant_id,
                Usuario.ativo == True,
            )
            .all()
        )

    def historico(self, patrimonio_id: int) -> List[Movimentacao]:
        return (
            self.db.query(Movimentacao)
            .filter(
                Movimentacao.patrimonio_id == patrimonio_id,
                Movimentacao.tenant_id == self.tenant_id,
            )
            .order_by(Movimentacao.created_at.desc())
            .all()
        )

    def criar(self, dados: PatrimonioCreate, usuario_id: int) -> Patrimonio:
        item = Patrimonio(**dados.model_dump(), tenant_id=self.tenant_id)
        self.db.add(item)
        self.db.flush()
        self._registrar_audit(
            usuario_id=usuario_id,
            acao="criar_patrimonio",
            registro_id=item.id,
            dados=dados.model_dump(mode="json"),
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def atualizar(
        self, patrimonio_id: int, dados: PatrimonioUpdate, usuario_id: int
    ) -> Optional[Patrimonio]:
        item = self.buscar_por_id(patrimonio_id)
        if not item:
            return None

        anteriores = {
            "setor": item.setor,
            "responsavel_id": item.responsavel_id,
            "status": item.status.value if item.status else None,
        }

        updates = dados.model_dump(exclude_unset=True)
        for campo, valor in updates.items():
            setattr(item, campo, valor)

        novos = {
            "setor": item.setor,
            "responsavel_id": item.responsavel_id,
            "status": item.status.value if item.status else None,
        }

        tipo = self._detectar_tipo_movimentacao(anteriores, novos)
        mov = Movimentacao(
            patrimonio_id=patrimonio_id,
            tenant_id=self.tenant_id,
            tipo=tipo,
            dados_anteriores=anteriores,
            dados_novos=novos,
            usuario_id=usuario_id,
        )
        self.db.add(mov)
        self._registrar_audit(
            usuario_id=usuario_id,
            acao="editar_patrimonio",
            registro_id=patrimonio_id,
            dados=updates,
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def _detectar_tipo_movimentacao(self, ant: dict, novo: dict) -> TipoMovimentacao:
        if ant["setor"] != novo["setor"]:
            return TipoMovimentacao.transferencia_setor
        if ant["responsavel_id"] != novo["responsavel_id"]:
            return TipoMovimentacao.troca_responsavel
        if ant["status"] != novo["status"]:
            return TipoMovimentacao.mudanca_status
        return TipoMovimentacao.edicao_dados

    def _registrar_audit(
        self, usuario_id: int, acao: str, registro_id: int, dados: dict
    ):
        log = AuditLog(
            tenant_id=self.tenant_id,
            usuario_id=usuario_id,
            acao=acao,
            tabela="patrimonios",
            registro_id=registro_id,
            dados=dados,
        )
        self.db.add(log)

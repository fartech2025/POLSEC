"""
RBAC Service — verifica se um funcionário tem permissão para executar
uma ação em um determinado módulo, com base nas permissões do seu cargo.

Estrutura de permissoes (JSON no Cargo):
    {
      "chamados":     ["criar", "ver", "editar", "cancelar", "aprovar"],
      "orcamentos":   ["criar", "ver", "aprovar", "rejeitar"],
      "pecas":        ["ver", "criar", "editar"],
      "patrimonios":  ["ver", "criar", "editar", "baixar"],
      "funcionarios": ["ver", "criar", "editar"],
      "financeiro":   ["ver", "aprovar"]
    }

Uso:
    rbac = RBACService(db)
    rbac.exigir(funcionario, modulo="chamados", acao="aprovar")   # levanta 403 se negado
    ok = rbac.tem_permissao(funcionario, "orcamentos", "aprovar") # bool
"""
import logging
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.funcionario import Funcionario

logger = logging.getLogger(__name__)


class RBACService:
    def __init__(self, db: Session):
        self.db = db

    # ── API principal ─────────────────────────────────────────────────────────

    def tem_permissao(self, funcionario: Funcionario, modulo: str, acao: str) -> bool:
        """Retorna True se o funcionário tem a ação permitida no módulo."""
        if funcionario is None or funcionario.cargo is None:
            return False
        permissoes: dict = funcionario.cargo.permissoes or {}
        acoes_modulo: list = permissoes.get(modulo, [])
        return acao in acoes_modulo

    def exigir(self, funcionario: Funcionario, modulo: str, acao: str) -> None:
        """Lança HTTP 403 se o funcionário não tiver a permissão exigida."""
        if not self.tem_permissao(funcionario, modulo, acao):
            cargo_nome = funcionario.cargo.nome if funcionario and funcionario.cargo else "sem cargo"
            logger.warning(
                "RBAC negado: funcionario=%s cargo=%s modulo=%s acao=%s",
                funcionario.id if funcionario else "?",
                cargo_nome,
                modulo,
                acao,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão negada: '{acao}' em '{modulo}' não autorizada para o cargo '{cargo_nome}'.",
            )

    def nivel_minimo(self, funcionario: Funcionario, nivel: int) -> bool:
        """
        Retorna True se o funcionário está em cargo de nível hierárquico
        igual ou superior ao exigido (número menor = hierarquia mais alta).
        Ex: nivel=3 (Coordenador) → passa Diretor(1), Gerente(2), Coordenador(3).
        """
        if funcionario is None or funcionario.cargo is None:
            return False
        return funcionario.cargo.nivel_hierarquico <= nivel

    def exigir_nivel(self, funcionario: Funcionario, nivel: int) -> None:
        """Lança HTTP 403 se o funcionário estiver abaixo do nível exigido."""
        if not self.nivel_minimo(funcionario, nivel):
            atual = funcionario.cargo.nivel_hierarquico if funcionario and funcionario.cargo else 99
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Nível hierárquico insuficiente: exigido ≤{nivel}, atual {atual}.",
            )

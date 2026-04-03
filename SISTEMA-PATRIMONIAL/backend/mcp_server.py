"""
MCP Server — POLSEC Patrimonial
Expõe as ferramentas do sistema como MCP Tools para uso por agentes externos
(Claude Desktop, outros clientes MCP, etc).

Uso:
    python mcp_server.py

Configurar no Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
{
  "mcpServers": {
    "polsec-patrimonial": {
      "command": "python",
      "args": ["/caminho/para/mcp_server.py"]
    }
  }
}
"""
import sys
import os
import json

# Adiciona o diretório do backend ao path
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func

from app.database import SessionLocal
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.movimentacao import Movimentacao
from app.models.usuario import Usuario

mcp = FastMCP("polsec-patrimonial")


def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ─── Tools MCP ───────────────────────────────────────────────────────────────

@mcp.tool()
def obter_estatisticas_patrimoniais() -> str:
    """
    Retorna estatísticas gerais do acervo patrimonial da POLSEC:
    total de bens, distribuição por status e top setores.
    """
    db = SessionLocal()
    try:
        total = db.query(func.count(Patrimonio.id)).scalar()
        por_status = {
            s.value: db.query(func.count(Patrimonio.id))
            .filter(Patrimonio.status == s)
            .scalar()
            for s in StatusPatrimonio
        }
        por_setor = (
            db.query(Patrimonio.setor, func.count(Patrimonio.id))
            .group_by(Patrimonio.setor)
            .order_by(func.count(Patrimonio.id).desc())
            .limit(10)
            .all()
        )
        resultado = {
            "total_bens": total,
            "por_status": por_status,
            "top_setores": [{"setor": s, "quantidade": c} for s, c in por_setor],
        }
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    finally:
        db.close()


@mcp.tool()
def buscar_patrimonios(
    busca: str = None,
    setor: str = None,
    status: str = None,
    limite: int = 10,
) -> str:
    """
    Busca bens patrimoniais com filtros opcionais.

    Args:
        busca: Termo para busca por código ou descrição
        setor: Filtrar por setor (ex: Administrativo, TI)
        status: Filtrar por status (ativo, manutencao, baixado, extraviado)
        limite: Número máximo de registros (padrão: 10)
    """
    db = SessionLocal()
    try:
        query = db.query(Patrimonio)
        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                Patrimonio.codigo.ilike(termo) | Patrimonio.descricao.ilike(termo)
            )
        if setor:
            query = query.filter(Patrimonio.setor == setor)
        if status:
            query = query.filter(Patrimonio.status == StatusPatrimonio(status))

        itens = query.limit(limite).all()
        resultado = [
            {
                "id": i.id,
                "codigo": i.codigo,
                "descricao": i.descricao,
                "categoria": i.categoria,
                "setor": i.setor,
                "localizacao": i.localizacao,
                "status": i.status.value,
                "responsavel": i.responsavel.nome if i.responsavel else None,
                "valor": float(i.valor) if i.valor else None,
            }
            for i in itens
        ]
        return json.dumps(
            {"total": len(resultado), "bens": resultado},
            ensure_ascii=False,
            indent=2,
        )
    finally:
        db.close()


@mcp.tool()
def obter_patrimonio(codigo: str) -> str:
    """
    Retorna os dados completos de um bem patrimonial pelo código.

    Args:
        codigo: Código único do patrimônio (ex: PAT-001)
    """
    db = SessionLocal()
    try:
        item = db.query(Patrimonio).filter(Patrimonio.codigo == codigo).first()
        if not item:
            return json.dumps({"erro": f"Patrimônio '{codigo}' não encontrado"})
        resultado = {
            "id": item.id,
            "codigo": item.codigo,
            "descricao": item.descricao,
            "categoria": item.categoria,
            "setor": item.setor,
            "localizacao": item.localizacao,
            "status": item.status.value,
            "responsavel": item.responsavel.nome if item.responsavel else None,
            "valor": float(item.valor) if item.valor else None,
            "data_aquisicao": item.data_aquisicao.strftime("%d/%m/%Y") if item.data_aquisicao else None,
            "observacoes": item.observacoes,
            "cadastrado_em": item.created_at.strftime("%d/%m/%Y"),
        }
        return json.dumps(resultado, ensure_ascii=False, indent=2)
    finally:
        db.close()


@mcp.tool()
def listar_movimentacoes(patrimonio_id: int = None, limite: int = 20) -> str:
    """
    Lista o histórico de movimentações do acervo.

    Args:
        patrimonio_id: ID do patrimônio para filtrar (opcional)
        limite: Número de registros (padrão: 20)
    """
    db = SessionLocal()
    try:
        query = db.query(Movimentacao)
        if patrimonio_id:
            query = query.filter(Movimentacao.patrimonio_id == patrimonio_id)
        movs = query.order_by(Movimentacao.created_at.desc()).limit(limite).all()
        resultado = [
            {
                "id": m.id,
                "patrimonio_codigo": m.patrimonio.codigo if m.patrimonio else None,
                "tipo": m.tipo.value,
                "descricao": m.descricao,
                "usuario": m.usuario.nome if m.usuario else None,
                "data": m.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for m in movs
        ]
        return json.dumps({"movimentacoes": resultado}, ensure_ascii=False, indent=2)
    finally:
        db.close()


@mcp.tool()
def listar_setores() -> str:
    """Retorna todos os setores com bens patrimoniais cadastrados."""
    db = SessionLocal()
    try:
        setores = (
            db.query(Patrimonio.setor, func.count(Patrimonio.id))
            .group_by(Patrimonio.setor)
            .order_by(func.count(Patrimonio.id).desc())
            .all()
        )
        return json.dumps(
            [{"setor": s, "total": c} for s, c in setores],
            ensure_ascii=False,
            indent=2,
        )
    finally:
        db.close()


# ─── Resources MCP ───────────────────────────────────────────────────────────

@mcp.resource("polsec://dashboard")
def resource_dashboard() -> str:
    """Snapshot do dashboard patrimonial."""
    db = SessionLocal()
    try:
        total = db.query(func.count(Patrimonio.id)).scalar()
        por_status = {
            s.value: db.query(func.count(Patrimonio.id))
            .filter(Patrimonio.status == s)
            .scalar()
            for s in StatusPatrimonio
        }
        return json.dumps(
            {"total": total, "status": por_status},
            ensure_ascii=False,
            indent=2,
        )
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()

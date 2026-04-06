"""
LLM Service — Integração com Claude (Anthropic)
Assistente inteligente com acesso às ferramentas do sistema patrimonial via tool_use.
"""
import json
from typing import AsyncGenerator
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

import anthropic

from app.config import settings
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.movimentacao import Movimentacao

# ─── Definição das ferramentas Tool-Use ──────────────────────────────────────

FERRAMENTAS = [
    {
        "name": "buscar_patrimonios",
        "description": (
            "Busca e lista bens patrimoniais com filtros opcionais. "
            "Use para responder perguntas sobre bens cadastrados, como quantos existem, "
            "quais estão em determinado setor ou status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "busca": {
                    "type": "string",
                    "description": "Termo para busca por código ou descrição do bem",
                },
                "setor": {
                    "type": "string",
                    "description": "Filtrar por setor específico",
                },
                "status": {
                    "type": "string",
                    "enum": ["ativo", "manutencao", "baixado", "extraviado"],
                    "description": "Filtrar por status do bem",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de registros a retornar (padrão: 10)",
                },
            },
        },
    },
    {
        "name": "obter_estatisticas",
        "description": (
            "Retorna estatísticas gerais do acervo patrimonial: "
            "total de bens, contagem por status, distribuição por setor."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "listar_movimentacoes",
        "description": (
            "Lista o histórico de movimentações de bens (transferências, trocas de responsável, "
            "mudanças de status). Use para consultar histórico de um bem específico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patrimonio_id": {
                    "type": "integer",
                    "description": "ID do patrimônio para filtrar movimentações",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número de registros (padrão: 15)",
                },
            },
        },
    },
    {
        "name": "buscar_patrimonio_por_codigo",
        "description": "Busca um bem patrimonial pelo seu código único.",
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo": {
                    "type": "string",
                    "description": "Código único do patrimônio (ex: PAT-001)",
                }
            },
            "required": ["codigo"],
        },
    },
]

SYSTEM_PROMPT = """Você é o Assistente Digital de Gestão Patrimonial da POLSEC.
Você tem acesso direto ao sistema de controle patrimonial via ferramentas.

Suas responsabilidades:
- Responder perguntas sobre o acervo patrimonial
- Consultar dados em tempo real usando as ferramentas disponíveis
- Gerar relatórios e análises sobre os bens
- Sugerir ações baseadas nos dados encontrados

Diretrizes:
- Sempre consulte os dados antes de responder perguntas factuais
- Seja objetivo e apresente números quando relevante
- Use linguagem profissional em português brasileiro
- Formate listas e tabelas quando houver múltiplos itens"""


# ─── Execução das ferramentas ─────────────────────────────────────────────────


def executar_ferramenta(nome: str, argumentos: dict, db: Session, tenant_id: str) -> str:
    if nome == "buscar_patrimonios":
        return _buscar_patrimonios(db, tenant_id, **argumentos)
    elif nome == "obter_estatisticas":
        return _obter_estatisticas(db, tenant_id)
    elif nome == "listar_movimentacoes":
        return _listar_movimentacoes(db, tenant_id, **argumentos)
    elif nome == "buscar_patrimonio_por_codigo":
        return _buscar_por_codigo(db, tenant_id, **argumentos)
    return json.dumps({"erro": f"Ferramenta '{nome}' não encontrada"})


def _buscar_patrimonios(
    db: Session,
    tenant_id: str,
    busca: str = None,
    setor: str = None,
    status: str = None,
    limite: int = 10,
) -> str:
    query = db.query(Patrimonio).options(
        selectinload(Patrimonio.responsavel)
    ).filter(Patrimonio.tenant_id == tenant_id)
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
        {"total_retornado": len(resultado), "bens": resultado}, ensure_ascii=False
    )


def _obter_estatisticas(db: Session, tenant_id: str) -> str:
    total = (
        db.query(func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .scalar()
    )
    por_status = (
        db.query(Patrimonio.status, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .group_by(Patrimonio.status)
        .all()
    )
    por_setor = (
        db.query(Patrimonio.setor, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .group_by(Patrimonio.setor)
        .order_by(func.count(Patrimonio.id).desc())
        .limit(10)
        .all()
    )
    resultado = {
        "total_bens": total,
        "por_status": {s.value: c for s, c in por_status},
        "top_setores": [{"setor": s, "quantidade": c} for s, c in por_setor],
    }
    return json.dumps(resultado, ensure_ascii=False)


def _listar_movimentacoes(
    db: Session, tenant_id: str, patrimonio_id: int = None, limite: int = 15
) -> str:
    query = db.query(Movimentacao).options(
        selectinload(Movimentacao.patrimonio),
        selectinload(Movimentacao.usuario),
    ).filter(Movimentacao.tenant_id == tenant_id)
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
    return json.dumps({"movimentacoes": resultado}, ensure_ascii=False)


def _buscar_por_codigo(db: Session, tenant_id: str, codigo: str) -> str:
    item = (
        db.query(Patrimonio)
        .filter(Patrimonio.tenant_id == tenant_id, Patrimonio.codigo == codigo)
        .first()
    )
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
        "data_aquisicao": (
            item.data_aquisicao.strftime("%d/%m/%Y") if item.data_aquisicao else None
        ),
        "observacoes": item.observacoes,
        "cadastrado_em": item.created_at.strftime("%d/%m/%Y"),
    }
    return json.dumps(resultado, ensure_ascii=False)


# ─── Loop agentico com streaming ─────────────────────────────────────────────


async def chat_stream(
    mensagens: list[dict], db: Session, tenant_id: str
) -> AsyncGenerator[str, None]:
    """
    Gera resposta do assistente com streaming via SSE.
    Executa o loop agentico: Claude → tool_use → executa → retorna resultado → Claude.
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    historico = list(mensagens)

    while True:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8000,
            thinking={"type": "enabled", "budget_tokens": 5000},
            system=SYSTEM_PROMPT,
            tools=FERRAMENTAS,
            messages=historico,
        ) as stream:
            for evento in stream:
                if (
                    evento.type == "content_block_delta"
                    and hasattr(evento.delta, "text")
                ):
                    chunk = evento.delta.text
                    yield f"data: {json.dumps({'tipo': 'texto', 'conteudo': chunk})}\n\n"

            mensagem_final = stream.get_final_message()

        if mensagem_final.stop_reason != "tool_use":
            yield f"data: {json.dumps({'tipo': 'fim'})}\n\n"
            break

        tool_uses = [b for b in mensagem_final.content if b.type == "tool_use"]
        historico.append({"role": "assistant", "content": mensagem_final.content})

        resultados = []
        for tu in tool_uses:
            yield f"data: {json.dumps({'tipo': 'ferramenta', 'nome': tu.name})}\n\n"
            resultado = executar_ferramenta(tu.name, tu.input, db, tenant_id)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": resultado,
                }
            )

        historico.append({"role": "user", "content": resultados})

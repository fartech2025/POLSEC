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
from app.models.faturamento import FaturamentoHistorico
from app.models.chamado import Chamado
from app.models.filial import Filial
from app.models.funcionario import Funcionario
from app.models.orcamento import Orcamento

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
    {
        "name": "consultar_faturamento",
        "description": (
            "Consulta o histórico de faturamento mensal por unidade. "
            "Use para responder perguntas sobre valores faturados, comparar períodos, "
            "ver ranking de unidades por faturamento ou buscar uma unidade específica. "
            "Dados disponíveis: out/2022 até mar/2026 — 31 unidades prisionais (EMTEL)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unidade": {
                    "type": "string",
                    "description": "Nome parcial da unidade/filial para filtrar (ex: 'Franco da Rocha', 'CDP')",
                },
                "mes": {
                    "type": "integer",
                    "description": "Mês para filtrar (1-12)",
                },
                "ano": {
                    "type": "integer",
                    "description": "Ano para filtrar (ex: 2025)",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de registros a retornar (padrão: 20)",
                },
            },
        },
    },
    {
        "name": "estatisticas_faturamento",
        "description": (
            "Retorna estatísticas consolidadas de faturamento: total geral, média mensal, "
            "ranking das unidades com maior faturamento, evolução por ano e mês com maiores valores. "
            "Use para perguntas como 'quanto foi faturado no total', 'qual unidade fatura mais', "
            "'qual foi o melhor mês'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ano": {
                    "type": "integer",
                    "description": "Filtrar por ano específico (opcional)",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Quantas unidades no ranking (padrão: 10)",
                },
            },
        },
    },
    {
        "name": "listar_chamados",
        "description": (
            "Lista chamados de manutenção com filtros opcionais. "
            "Use para perguntas sobre chamados abertos, pendentes, concluídos ou por prioridade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["aberto", "em_atendimento", "aguardando_pecas", "em_execucao", "concluido", "cancelado", "reaberto"],
                    "description": "Filtrar por status do chamado",
                },
                "prioridade": {
                    "type": "string",
                    "enum": ["baixa", "media", "alta", "critica"],
                    "description": "Filtrar por prioridade",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de registros (padrão: 15)",
                },
            },
        },
    },
    {
        "name": "listar_filiais",
        "description": (
            "Lista as unidades/filiais cadastradas no sistema. "
            "Use para saber quantas unidades existem, seus nomes ou para localizar uma unidade específica."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "busca": {
                    "type": "string",
                    "description": "Termo para filtrar pelo nome da unidade",
                },
            },
        },
    },
    {
        "name": "resumo_geral",
        "description": (
            "Retorna um resumo consolidado de toda a operação: patrimônios, chamados, "
            "faturamento e unidades. Use como ponto de partida para análises gerais ou "
            "quando o usuário perguntar sobre o estado geral do sistema."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

SYSTEM_PROMPT = """Você é o Assistente Digital de Gestão da POLSEC — sistema integrado de controle patrimonial, manutenção e faturamento de unidades prisionais.
Você tem acesso direto ao sistema via ferramentas e pode consultar dados em tempo real.

Capacidades:
- **Patrimônio**: consultar bens, status (ativo/manutenção/baixado/extraviado), setores, valores, histórico de movimentações
- **Faturamento**: histórico mensal por unidade (out/2022–mar/2026), totais, ranking, evolução temporal — 31 unidades prisionais, R$ 180 milhões de histórico
- **Chamados**: manutenções abertas, em andamento, concluídas, por prioridade
- **Unidades**: 33 filiais cadastradas (unidades prisionais do estado de São Paulo)
- **Visão geral**: resumo consolidado de toda a operação

Diretrizes:
- Sempre consulte os dados reais antes de responder perguntas factuais
- Para perguntas sobre faturamento, use `consultar_faturamento` ou `estatisticas_faturamento`
- Para visão geral ou quando não souber por onde começar, use `resumo_geral`
- Apresente valores em reais (R$ 1.234.567,89) com separadores de milhar
- Seja objetivo: use tabelas e listas quando houver múltiplos itens
- Use linguagem profissional em português brasileiro
- Ao citar unidades prisionais, use o nome oficial do sistema (ex: CDP SÃO PAULO, PEP I)"""


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
    elif nome == "consultar_faturamento":
        return _consultar_faturamento(db, tenant_id, **argumentos)
    elif nome == "estatisticas_faturamento":
        return _estatisticas_faturamento(db, tenant_id, **argumentos)
    elif nome == "listar_chamados":
        return _listar_chamados(db, tenant_id, **argumentos)
    elif nome == "listar_filiais":
        return _listar_filiais(db, tenant_id, **argumentos)
    elif nome == "resumo_geral":
        return _resumo_geral(db, tenant_id)
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


def _consultar_faturamento(
    db: Session,
    tenant_id: str,
    unidade: str = None,
    mes: int = None,
    ano: int = None,
    limite: int = 20,
) -> str:
    query = db.query(FaturamentoHistorico).filter(
        FaturamentoHistorico.tenant_id == tenant_id
    )
    if unidade:
        query = query.filter(FaturamentoHistorico.filial_nome.ilike(f"%{unidade}%"))
    if mes:
        query = query.filter(FaturamentoHistorico.mes == mes)
    if ano:
        query = query.filter(FaturamentoHistorico.ano == ano)

    registros = (
        query.order_by(
            FaturamentoHistorico.ano.desc(),
            FaturamentoHistorico.mes.desc(),
            FaturamentoHistorico.valor_total.desc(),
        )
        .limit(limite)
        .all()
    )
    resultado = [
        {
            "unidade": r.filial_nome,
            "periodo": f"{r.mes:02d}/{r.ano}",
            "valor_total": float(r.valor_total),
            "valor_mao_obra": float(r.valor_mao_obra),
            "valor_pecas": float(r.valor_pecas),
            "chamados_count": r.chamados_count,
            "origem": r.origem,
        }
        for r in registros
    ]
    total_registros = query.count()
    return json.dumps(
        {"total_registros": total_registros, "retornados": len(resultado), "faturamentos": resultado},
        ensure_ascii=False,
    )


def _estatisticas_faturamento(
    db: Session, tenant_id: str, ano: int = None, top_n: int = 10
) -> str:
    query_base = db.query(FaturamentoHistorico).filter(
        FaturamentoHistorico.tenant_id == tenant_id
    )
    if ano:
        query_base = query_base.filter(FaturamentoHistorico.ano == ano)

    total_geral = (
        db.query(func.sum(FaturamentoHistorico.valor_total))
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .scalar() or 0
    )
    # Média mensal (soma / número de meses distintos)
    meses_distintos = (
        db.query(func.count(func.distinct(
            func.concat(FaturamentoHistorico.ano, '-', FaturamentoHistorico.mes)
        )))
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .scalar() or 1
    )
    # Totais do filtro (se ano especificado)
    total_filtrado = query_base.with_entities(func.sum(FaturamentoHistorico.valor_total)).scalar() or 0

    # Ranking por unidade
    ranking_q = (
        db.query(
            FaturamentoHistorico.filial_nome,
            func.sum(FaturamentoHistorico.valor_total).label("total"),
            func.count(FaturamentoHistorico.id).label("meses"),
        )
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
    )
    if ano:
        ranking_q = ranking_q.filter(FaturamentoHistorico.ano == ano)
    ranking = (
        ranking_q
        .group_by(FaturamentoHistorico.filial_nome)
        .order_by(func.sum(FaturamentoHistorico.valor_total).desc())
        .limit(top_n)
        .all()
    )

    # Evolução por ano
    por_ano = (
        db.query(
            FaturamentoHistorico.ano,
            func.sum(FaturamentoHistorico.valor_total).label("total"),
            func.count(FaturamentoHistorico.id).label("registros"),
        )
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .group_by(FaturamentoHistorico.ano)
        .order_by(FaturamentoHistorico.ano)
        .all()
    )

    # Mês com maior faturamento geral
    melhor_mes = (
        db.query(
            FaturamentoHistorico.mes,
            FaturamentoHistorico.ano,
            func.sum(FaturamentoHistorico.valor_total).label("total"),
        )
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .group_by(FaturamentoHistorico.mes, FaturamentoHistorico.ano)
        .order_by(func.sum(FaturamentoHistorico.valor_total).desc())
        .first()
    )

    resultado = {
        "total_geral_historico": float(total_geral),
        "total_periodo_filtrado": float(total_filtrado),
        "media_mensal_historica": float(total_geral / meses_distintos),
        "total_meses_disponíveis": meses_distintos,
        "periodo_cobertura": "out/2022 a mar/2026",
        "melhor_mes": (
            {"periodo": f"{melhor_mes.mes:02d}/{melhor_mes.ano}", "total": float(melhor_mes.total)}
            if melhor_mes else None
        ),
        "ranking_unidades": [
            {"unidade": r.filial_nome, "total": float(r.total), "meses": r.meses}
            for r in ranking
        ],
        "evolucao_anual": [
            {"ano": r.ano, "total": float(r.total), "registros": r.registros}
            for r in por_ano
        ],
    }
    return json.dumps(resultado, ensure_ascii=False)


def _listar_chamados(
    db: Session,
    tenant_id: str,
    status: str = None,
    prioridade: str = None,
    limite: int = 15,
) -> str:
    query = db.query(Chamado).filter(Chamado.tenant_id == tenant_id)
    if status:
        query = query.filter(Chamado.status == status)
    if prioridade:
        query = query.filter(Chamado.prioridade == prioridade)

    total = query.count()

    # Contagem por status
    por_status = (
        db.query(Chamado.status, func.count(Chamado.id))
        .filter(Chamado.tenant_id == tenant_id)
        .group_by(Chamado.status)
        .all()
    )

    chamados = (
        query.order_by(Chamado.created_at.desc()).limit(limite).all()
    )
    resultado = {
        "total_filtrado": total,
        "por_status": {str(s): c for s, c in por_status},
        "chamados": [
            {
                "id": c.id,
                "titulo": c.titulo,
                "status": str(c.status),
                "prioridade": str(c.prioridade),
                "aberto_em": c.created_at.strftime("%d/%m/%Y"),
            }
            for c in chamados
        ],
    }
    return json.dumps(resultado, ensure_ascii=False)


def _listar_filiais(
    db: Session, tenant_id: str, busca: str = None
) -> str:
    query = db.query(Filial).filter(Filial.tenant_id == tenant_id)
    if busca:
        query = query.filter(Filial.nome.ilike(f"%{busca}%"))
    filiais = query.order_by(Filial.nome).all()
    resultado = {
        "total": len(filiais),
        "unidades": [{"id": f.id, "nome": f.nome} for f in filiais],
    }
    return json.dumps(resultado, ensure_ascii=False)


def _resumo_geral(db: Session, tenant_id: str) -> str:
    # Patrimônios
    total_pats = db.query(func.count(Patrimonio.id)).filter(Patrimonio.tenant_id == tenant_id).scalar() or 0
    pats_ativos = (
        db.query(func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id, Patrimonio.status == StatusPatrimonio.ativo)
        .scalar() or 0
    )
    # Chamados
    total_chamados = db.query(func.count(Chamado.id)).filter(Chamado.tenant_id == tenant_id).scalar() or 0
    chamados_abertos = (
        db.query(func.count(Chamado.id))
        .filter(Chamado.tenant_id == tenant_id, Chamado.status == "aberto")
        .scalar() or 0
    )
    # Faturamento
    total_fat = (
        db.query(func.sum(FaturamentoHistorico.valor_total))
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .scalar() or 0
    )
    ultimo_mes = (
        db.query(
            FaturamentoHistorico.mes,
            FaturamentoHistorico.ano,
            func.sum(FaturamentoHistorico.valor_total).label("total"),
            func.count(FaturamentoHistorico.id).label("unidades"),
        )
        .filter(FaturamentoHistorico.tenant_id == tenant_id)
        .group_by(FaturamentoHistorico.mes, FaturamentoHistorico.ano)
        .order_by(FaturamentoHistorico.ano.desc(), FaturamentoHistorico.mes.desc())
        .first()
    )
    # Filiais
    total_filiais = db.query(func.count(Filial.id)).filter(Filial.tenant_id == tenant_id).scalar() or 0

    resultado = {
        "patrimônios": {
            "total": total_pats,
            "ativos": pats_ativos,
            "em_manutencao_ou_baixados": total_pats - pats_ativos,
        },
        "chamados": {
            "total_historico": total_chamados,
            "abertos_agora": chamados_abertos,
        },
        "faturamento": {
            "total_historico": float(total_fat),
            "periodo": "out/2022 a mar/2026",
            "ultimo_mes_fechado": (
                {
                    "periodo": f"{ultimo_mes.mes:02d}/{ultimo_mes.ano}",
                    "valor": float(ultimo_mes.total),
                    "unidades": ultimo_mes.unidades,
                }
                if ultimo_mes else None
            ),
        },
        "unidades": {"total_filiais": total_filiais},
    }
    return json.dumps(resultado, ensure_ascii=False)


# ─── Loop agentico com streaming ─────────────────────────────────────────────


async def chat_stream(
    mensagens: list[dict],
    db: Session,
    tenant_id: str,
    api_key: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Gera resposta do assistente com streaming via SSE.
    Executa o loop agentico: Claude → tool_use → executa → retorna resultado → Claude.

    api_key: chave do tenant (preferencial). Recai na variável de ambiente ANTHROPIC_API_KEY.
    """
    resolved_key = api_key or settings.ANTHROPIC_API_KEY
    client = anthropic.Anthropic(api_key=resolved_key)

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

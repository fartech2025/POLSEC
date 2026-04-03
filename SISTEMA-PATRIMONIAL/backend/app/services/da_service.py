"""
DA Service — Data Analytics com LLM
Gera insights automáticos sobre o acervo patrimonial usando Claude.
"""
import json
from sqlalchemy.orm import Session
from sqlalchemy import func

import anthropic

from app.config import settings
from app.models.patrimonio import Patrimonio, StatusPatrimonio
from app.models.movimentacao import Movimentacao


def coletar_dados_analiticos(db: Session, tenant_id: str) -> dict:
    """Coleta snapshot completo do acervo do tenant para análise."""
    total = (
        db.query(func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .scalar()
    )

    por_status = {
        s.value: db.query(func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id, Patrimonio.status == s)
        .scalar()
        for s in StatusPatrimonio
    }

    por_setor = (
        db.query(Patrimonio.setor, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .group_by(Patrimonio.setor)
        .order_by(func.count(Patrimonio.id).desc())
        .all()
    )

    por_categoria = (
        db.query(Patrimonio.categoria, func.count(Patrimonio.id))
        .filter(Patrimonio.tenant_id == tenant_id)
        .group_by(Patrimonio.categoria)
        .order_by(func.count(Patrimonio.id).desc())
        .limit(8)
        .all()
    )

    valor_total = (
        db.query(func.sum(Patrimonio.valor))
        .filter(
            Patrimonio.tenant_id == tenant_id,
            Patrimonio.status == StatusPatrimonio.ativo,
        )
        .scalar()
    )

    sem_responsavel = (
        db.query(func.count(Patrimonio.id))
        .filter(
            Patrimonio.tenant_id == tenant_id,
            Patrimonio.responsavel_id.is_(None),
        )
        .scalar()
    )

    movimentacoes_recentes = (
        db.query(Movimentacao)
        .filter(Movimentacao.tenant_id == tenant_id)
        .order_by(Movimentacao.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "total_bens": total,
        "por_status": por_status,
        "por_setor": [{"setor": s, "qtd": c} for s, c in por_setor],
        "por_categoria": [{"categoria": c, "qtd": q} for c, q in por_categoria],
        "valor_total_ativos": float(valor_total) if valor_total else 0,
        "sem_responsavel": sem_responsavel,
        "movimentacoes_recentes": [
            {
                "tipo": m.tipo.value,
                "patrimonio": m.patrimonio.codigo if m.patrimonio else "?",
                "data": m.created_at.strftime("%d/%m/%Y"),
            }
            for m in movimentacoes_recentes
        ],
    }


def gerar_insights(db: Session, tenant_id: str) -> dict:
    """
    Envia os dados do acervo para Claude e retorna análise estruturada
    com insights, alertas e recomendações.
    """
    dados = coletar_dados_analiticos(db, tenant_id)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = f"""Analise os dados do acervo patrimonial da POLSEC abaixo e gere um relatório analítico completo.

DADOS DO ACERVO:
{json.dumps(dados, ensure_ascii=False, indent=2)}

Retorne um JSON válido com exatamente esta estrutura:
{{
  "resumo_executivo": "parágrafo com visão geral do acervo",
  "indicadores_chave": [
    {{"titulo": "...", "valor": "...", "tendencia": "positivo|negativo|neutro", "descricao": "..."}}
  ],
  "alertas": [
    {{"nivel": "critico|atencao|info", "titulo": "...", "descricao": "...", "acao_recomendada": "..."}}
  ],
  "insights": [
    {{"categoria": "...", "insight": "...", "impacto": "alto|medio|baixo"}}
  ],
  "recomendacoes": [
    {{"prioridade": 1, "titulo": "...", "descricao": "...", "prazo": "imediato|curto_prazo|medio_prazo"}}
  ],
  "score_gestao": {{
    "nota": 0,
    "descricao": "...",
    "pontos_positivos": ["..."],
    "pontos_melhoria": ["..."]
  }}
}}

Seja preciso, use os números reais dos dados. score_gestao.nota deve ser de 0 a 100."""

    resposta = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8000,
        thinking={"type": "enabled", "budget_tokens": 5000},
        messages=[{"role": "user", "content": prompt}],
    )

    texto = next(b.text for b in resposta.content if b.type == "text")

    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0].strip()
    elif "```" in texto:
        texto = texto.split("```")[1].split("```")[0].strip()

    resultado = json.loads(texto)
    resultado["dados_brutos"] = dados
    return resultado

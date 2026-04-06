"""
Security Audit Engine — Varredura automatizada diária.

Checks implementados:
  1. contas_stagnadas    — ativo=True mas updated_at > 90 dias (contas esquecidas)
  2. privilegios         — lista superadmins e administradores ativos; alerta se >3 superadmins
  3. volume_anomalo      — tenant com z-score > 3σ em audit_logs das últimas 24h (exfiltração?)
  4. inativos_com_uid    — ativo=False mas com supabase_uid (revogar no Supabase Auth)
  5. brute_force         — IPs bloqueados no módulo rate_limit (ataque em andamento)

Saída:
  - Log estruturado via logger "polsec.security.audit"
  - JSON em SEC_AUDIT_DIR / security_audit_YYYY-MM-DD.json  (padrão /tmp)

Execução:
  # Standalone:
  cd backend && python -m app.security.audit

  # Via cron (diário às 02:00):
  0 2 * * * cd /caminho/backend && .venv/bin/python -m app.security.audit >> /var/log/polsec-audit.log 2>&1
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.usuario import PerfilUsuario, Usuario

_log = logging.getLogger("polsec.security.audit")

AUDIT_REPORT_DIR = Path(os.getenv("SEC_AUDIT_DIR", "/tmp"))
_STALE_DAYS = 90          # dias sem atualização para considerar conta estagnada
_ANOMALY_SIGMA = 3.0      # desvios padrão para considerar volume anômalo


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def executar_auditoria() -> dict[str, Any]:
    """
    Executa todos os checks de segurança, persiste o relatório em JSON e
    retorna o dict do relatório.
    """
    relatorio: dict[str, Any] = {
        "gerado_em": _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "severidade_geral": "ok",
        "alertas": [],
        "checks": {},
    }
    alertas: list[dict] = []

    db: Session = SessionLocal()
    try:
        _check_contas_stagnadas(db, relatorio, alertas)
        _check_privilegios(db, relatorio, alertas)
        _check_volume_anomalo(db, relatorio, alertas)
        _check_inativos_com_uid(db, relatorio, alertas)
        _check_brute_force(relatorio, alertas)
    except Exception as exc:
        _log.error("Erro inesperado na auditoria: %s", exc, exc_info=True)
        relatorio["erro"] = str(exc)
    finally:
        db.close()

    relatorio["alertas"] = alertas
    relatorio["severidade_geral"] = _calcular_severidade(alertas)

    _persistir(relatorio)
    _logar_resumo(relatorio)
    return relatorio


# ── Checks individuais ────────────────────────────────────────────────────────

def _check_contas_stagnadas(db: Session, r: dict, alertas: list) -> None:
    """
    Contas ativas cujo updated_at é mais antigo que _STALE_DAYS.
    Indício de contas esquecidas que devem ser revisadas ou desativadas.
    """
    corte = _utcnow() - timedelta(days=_STALE_DAYS)
    stagnados = (
        db.query(Usuario)
        .filter(Usuario.ativo == True, Usuario.updated_at < corte)
        .order_by(Usuario.updated_at)
        .all()
    )
    r["checks"]["contas_stagnadas"] = len(stagnados)
    if stagnados:
        alertas.append({
            "check": "contas_stagnadas",
            "severidade": "medio",
            "mensagem": (
                f"{len(stagnados)} conta(s) ativa(s) sem atualização "
                f"há mais de {_STALE_DAYS} dias. Revisar e desativar se necessário."
            ),
            "detalhes": [
                {
                    "id": u.id,
                    "email": u.email,
                    "perfil": u.perfil.value,
                    "tenant_id": u.tenant_id,
                    "updated_at": u.updated_at.strftime("%Y-%m-%d") if u.updated_at else None,
                }
                for u in stagnados
            ],
        })


def _check_privilegios(db: Session, r: dict, alertas: list) -> None:
    """
    Lista usuários com perfil elevado (superadmin, administrador).
    Alerta se houver mais de 3 superadmins ativos — princípio do menor privilégio.
    """
    elevados = (
        db.query(Usuario)
        .filter(
            Usuario.ativo == True,
            Usuario.perfil.in_([PerfilUsuario.superadmin, PerfilUsuario.administrador]),
        )
        .all()
    )
    superadmins = [u for u in elevados if u.perfil == PerfilUsuario.superadmin]
    admins = [u for u in elevados if u.perfil == PerfilUsuario.administrador]

    r["checks"]["usuarios_privilegiados"] = len(elevados)
    r["checks"]["superadmins"] = [{"email": u.email, "id": u.id} for u in superadmins]

    if len(superadmins) > 3:
        alertas.append({
            "check": "excesso_superadmin",
            "severidade": "alto",
            "mensagem": (
                f"{len(superadmins)} contas superadmin ativas detectadas "
                "(limite recomendado: ≤3). Revisar e reduzir privilégios."
            ),
            "detalhes": [{"email": u.email, "id": u.id} for u in superadmins],
        })

    # Relatório informativo de admins por tenant
    tenants_map: dict[str, list[str]] = {}
    for u in admins:
        tenants_map.setdefault(u.tenant_id, []).append(u.email)
    r["checks"]["admins_por_tenant"] = tenants_map


def _check_volume_anomalo(db: Session, r: dict, alertas: list) -> None:
    """
    Detecta tenants com volume de eventos em audit_logs nas últimas 24h
    acima de 3 desvios padrão da média (possível exfiltração ou abuso).
    """
    janela = _utcnow() - timedelta(hours=24)
    resultados = (
        db.query(AuditLog.tenant_id, func.count(AuditLog.id).label("qtd"))
        .filter(AuditLog.created_at >= janela)
        .group_by(AuditLog.tenant_id)
        .all()
    )

    volume_map = {t: c for t, c in resultados}
    r["checks"]["audit_volume_24h"] = volume_map

    if len(resultados) < 2:
        return  # sem dados suficientes para análise estatística

    contagens = [c for _, c in resultados]
    media = sum(contagens) / len(contagens)
    desvio = (sum((x - media) ** 2 for x in contagens) / len(contagens)) ** 0.5

    if desvio == 0:
        return

    for tenant_id, qtd in resultados:
        z = (qtd - media) / desvio
        if z > _ANOMALY_SIGMA:
            alertas.append({
                "check": "volume_anomalo",
                "severidade": "alto",
                "mensagem": (
                    f"Tenant {tenant_id!r} com {qtd} eventos em 24h "
                    f"(z={z:.1f}σ acima da média de {media:.0f}). "
                    "Possível exfiltração ou abuso — investigar."
                ),
                "detalhes": {
                    "tenant_id": tenant_id,
                    "eventos_24h": qtd,
                    "media_plataforma": round(media, 1),
                    "z_score": round(z, 2),
                },
            })


def _check_inativos_com_uid(db: Session, r: dict, alertas: list) -> None:
    """
    Usuários com ativo=False que ainda possuem supabase_uid.
    Esses usuários ainda podem ter sessões ativas no Supabase Auth.
    Devem ser removidos via Supabase Admin API.
    """
    qtd = (
        db.query(func.count(Usuario.id))
        .filter(Usuario.ativo == False, Usuario.supabase_uid.isnot(None))
        .scalar()
    ) or 0

    r["checks"]["inativos_com_supabase_uid"] = qtd
    if qtd > 0:
        alertas.append({
            "check": "inativos_com_uid",
            "severidade": "baixo",
            "mensagem": (
                f"{qtd} usuário(s) desativado(s) ainda possuem supabase_uid. "
                "Revogar acesso no Supabase Auth para garantir isolamento de sessão."
            ),
        })


def _check_brute_force(r: dict, alertas: list) -> None:
    """
    Verifica IPs atualmente bloqueados pelo LoginRateLimitMiddleware.
    Indica ataque de força bruta em andamento.
    """
    try:
        from app.middleware.rate_limit import (
            _MAX_ATTEMPTS,
            _WINDOW,
            _tentativas,
        )

        agora = time.time()
        corte = agora - _WINDOW
        bloqueados = {
            ip: [t for t in ts if t > corte]
            for ip, ts in _tentativas.items()
        }
        bloqueados = {ip: ts for ip, ts in bloqueados.items() if len(ts) >= _MAX_ATTEMPTS}

        r["checks"]["ips_bloqueados"] = len(bloqueados)
        if bloqueados:
            alertas.append({
                "check": "brute_force",
                "severidade": "critico",
                "mensagem": (
                    f"{len(bloqueados)} IP(s) bloqueado(s) por exceder "
                    f"{_MAX_ATTEMPTS} tentativas de login em {_WINDOW // 60} min."
                ),
                "detalhes": {ip: len(ts) for ip, ts in bloqueados.items()},
            })
    except Exception as exc:
        _log.debug("Não foi possível verificar rate_limit: %s", exc)
        r["checks"]["ips_bloqueados"] = "indisponível (módulo não carregado)"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _calcular_severidade(alertas: list[dict]) -> str:
    if not alertas:
        return "ok"
    severidades = [a.get("severidade", "info") for a in alertas]
    for nivel in ("critico", "alto", "medio", "baixo"):
        if nivel in severidades:
            return nivel
    return "info"


def _persistir(relatorio: dict) -> None:
    AUDIT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    data = _utcnow().strftime("%Y-%m-%d")
    caminho = AUDIT_REPORT_DIR / f"security_audit_{data}.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    _log.info("Relatório de segurança gravado em %s", caminho)


def _logar_resumo(relatorio: dict) -> None:
    sev = relatorio.get("severidade_geral", "?")
    n = len(relatorio.get("alertas", []))
    nivel = (
        logging.CRITICAL if sev == "critico"
        else logging.ERROR if sev == "alto"
        else logging.WARNING if sev == "medio"
        else logging.INFO
    )
    _log.log(nivel, "SECURITY_AUDIT severidade=%-8s alertas=%d", sev.upper(), n)
    for alerta in relatorio.get("alertas", []):
        _log.warning(
            "  [%-8s] %-30s %s",
            alerta.get("severidade", "?").upper(),
            alerta.get("check", "?"),
            alerta.get("mensagem", ""),
        )


# ── Entrada standalone ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    resultado = executar_auditoria()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    sys.exit(0 if resultado.get("severidade_geral") in ("ok", "baixo", "info") else 1)

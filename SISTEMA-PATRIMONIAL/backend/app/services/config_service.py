"""
Config Service — configurações sensíveis por tenant.

Armazena dados no campo `configuracoes` (JSON Text) do modelo Tenant.
Chaves sensíveis (como API keys) são cifradas com Fernet (AES-128-CBC + HMAC-SHA256)
antes de persistir no banco.

Uso:
    from app.services.config_service import TenantConfigService

    svc = TenantConfigService(tenant)
    svc.set_llm_api_key(db, "sk-ant-...")
    key = svc.get_llm_api_key()          # retorna str | None
    masked = svc.get_llm_api_key_masked() # "sk-ant-...•••••••••••1234"
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings

_log = logging.getLogger("polsec.config_service")

# ── Fernet lazy-init ─────────────────────────────────────────────────────────
# Evita erro de import se SECRET_KEY ainda não estiver configurada.

def _fernet():
    """Retorna instância Fernet usando SECRET_KEY das settings."""
    from cryptography.fernet import Fernet, InvalidToken  # noqa: F401
    key = settings.SECRET_KEY
    if not key:
        raise RuntimeError(
            "SECRET_KEY não configurada. Defina SECRET_KEY no .env "
            "(gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> Optional[str]:
    try:
        from cryptography.fernet import InvalidToken
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as exc:
        _log.error("Falha ao descriptografar valor de configuração: %s", exc)
        return None


# ── Service ───────────────────────────────────────────────────────────────────

class TenantConfigService:
    """Wrapper de leitura/escrita de configs sensíveis de um tenant."""

    _KEY_LLM = "llm_api_key"          # chave no dict de configurações

    def __init__(self, tenant):
        self._tenant = tenant

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _load(self) -> dict:
        raw = self._tenant.configuracoes
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _save(self, db: Session, cfg: dict) -> None:
        self._tenant.configuracoes = json.dumps(cfg, ensure_ascii=False)
        db.add(self._tenant)
        db.commit()
        db.refresh(self._tenant)

    # ── API pública ───────────────────────────────────────────────────────────

    def get_llm_api_key(self) -> Optional[str]:
        """
        Retorna a chave Claude do tenant em plaintext, ou None se não configurada.
        Nunca deve ser enviada para o frontend.
        """
        cfg = self._load()
        encrypted = cfg.get(self._KEY_LLM)
        if not encrypted:
            return None
        return _decrypt(encrypted)

    def get_llm_api_key_masked(self) -> Optional[str]:
        """
        Retorna versão mascarada da chave para exibição segura no frontend.
        Exemplo: "sk-ant-api03-••••••••••••••••1234"
        """
        key = self.get_llm_api_key()
        if not key:
            return None
        prefix = key[:12] if len(key) > 12 else key[:4]
        suffix = key[-4:] if len(key) > 16 else "****"
        middle = "•" * 16
        return f"{prefix}{middle}{suffix}"

    def has_llm_api_key(self) -> bool:
        cfg = self._load()
        return bool(cfg.get(self._KEY_LLM))

    def set_llm_api_key(self, db: Session, api_key: str) -> None:
        """
        Cifra e persiste a chave Claude do tenant.
        A chave em plaintext nunca é salva no banco.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key não pode ser vazia.")
        api_key = api_key.strip()
        if not (api_key.startswith("sk-ant-") or api_key.startswith("sk-")):
            raise ValueError(
                "Chave Anthropic inválida. Deve começar com 'sk-ant-'."
            )
        cfg = self._load()
        cfg[self._KEY_LLM] = _encrypt(api_key)
        self._save(db, cfg)
        _log.info(
            "LLM API key atualizada para tenant %s (%s)",
            self._tenant.slug,
            self.get_llm_api_key_masked(),
        )

    def remove_llm_api_key(self, db: Session) -> None:
        cfg = self._load()
        cfg.pop(self._KEY_LLM, None)
        self._save(db, cfg)
        _log.info("LLM API key removida para tenant %s", self._tenant.slug)

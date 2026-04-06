from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Sistema Patrimonial POLSEC"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── Supabase ─────────────────────────────────────────────────────────────
    # URL do projeto: https://<project-id>.supabase.co
    SUPABASE_URL: str = ""
    # Chave anon (pública) — usada no client do frontend/auth
    SUPABASE_ANON_KEY: str = ""
    # Chave service_role (secreta) — usada no backend para operações admin
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    # String de conexão direta ao PostgreSQL do Supabase (via connection pooler)
    # Formato: postgresql+psycopg://postgres.<project-id>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
    DATABASE_URL: str = ""

    # ── JWT (Supabase usa RS256 — só precisamos do secret para validar) ───────
    # O Supabase assina com RS256; o JWKS fica em <SUPABASE_URL>/auth/v1/.well-known/jwks.json
    # Para simplificar usamos o JWT_SECRET do projeto (Settings > API > JWT Secret)
    SUPABASE_JWT_SECRET: str = ""

    # ── IA ───────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── Segurança ─────────────────────────────────────────────────────────────
    # Chave Fernet para cifrar valores sensíveis armazenados no banco (ex: API keys de tenants).
    # Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

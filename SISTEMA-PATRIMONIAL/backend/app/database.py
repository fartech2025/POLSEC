from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Supabase usa connection pooler (porta 6543 = transaction mode)
# Para migrações DDL usar porta 5432 (session mode)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_with_tenant(tenant_id: str):
    """
    Retorna uma session com o tenant_id configurado como variável de sessão
    para que as políticas RLS do Supabase funcionem corretamente.
    """
    db = SessionLocal()
    try:
        # Injeta o tenant_id na sessão PostgreSQL para uso pelas policies RLS
        db.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": tenant_id},
        )
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

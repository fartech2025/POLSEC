"""
Executa a migration 003_glosa_chamados usando o SQLAlchemy do próprio app.
Evita o timeout do SQL Editor do Supabase.

Uso: PYTHONPATH=. .venv/bin/python3 aplicar_migration_glosa.py
"""
import sys
from sqlalchemy import text
from app.database import engine

STATEMENTS = [
    # ── 1. Novos campos em chamados ──────────────────────────────────────────
    ("ADD numero_chamado",
     "ALTER TABLE chamados ADD COLUMN IF NOT EXISTS numero_chamado INTEGER"),
    ("ADD tipo_chamado",
     "ALTER TABLE chamados ADD COLUMN IF NOT EXISTS tipo_chamado VARCHAR(20) CHECK (tipo_chamado IN ('preventiva','corretiva'))"),
    ("ADD data_chegada_tecnico",
     "ALTER TABLE chamados ADD COLUMN IF NOT EXISTS data_chegada_tecnico TIMESTAMPTZ"),
    ("ADD justificativa_atraso",
     "ALTER TABLE chamados ADD COLUMN IF NOT EXISTS justificativa_atraso TEXT"),
    ("ADD codigo_unidade",
     "ALTER TABLE chamados ADD COLUMN IF NOT EXISTS codigo_unidade VARCHAR(10)"),

    # ── 2. Tabela glosa_chamados ─────────────────────────────────────────────
    ("CREATE glosa_chamados", """
        CREATE TABLE IF NOT EXISTS glosa_chamados (
            id                  SERIAL PRIMARY KEY,
            tenant_id           UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            chamado_id          INTEGER      REFERENCES chamados(id) ON DELETE SET NULL,
            filial_id           INTEGER      REFERENCES filiais(id) ON DELETE SET NULL,
            filial_nome         VARCHAR(150) NOT NULL,
            data_inicio         TIMESTAMPTZ  NOT NULL,
            data_fim            TIMESTAMPTZ,
            horas_indisponiveis NUMERIC(8,2),
            percentual_glosa    NUMERIC(5,2),
            valor_base          NUMERIC(12,2),
            valor_glosa         NUMERIC(12,2),
            status              VARCHAR(20) NOT NULL DEFAULT 'ativa'
                                    CHECK (status IN ('ativa','encerrada','contestada','cancelada')),
            observacoes         TEXT,
            motivo              TEXT,
            registrado_por_id   INTEGER REFERENCES funcionarios(id) ON DELETE SET NULL,
            encerrado_por_id    INTEGER REFERENCES funcionarios(id) ON DELETE SET NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    ("INDEX ix_glosa_tenant_status",
     "CREATE INDEX IF NOT EXISTS ix_glosa_tenant_status ON glosa_chamados (tenant_id, status)"),
    ("INDEX ix_glosa_filial",
     "CREATE INDEX IF NOT EXISTS ix_glosa_filial ON glosa_chamados (filial_id)"),
    ("INDEX ix_glosa_chamado",
     "CREATE INDEX IF NOT EXISTS ix_glosa_chamado ON glosa_chamados (chamado_id)"),
    ("INDEX ix_glosa_data_inicio",
     "CREATE INDEX IF NOT EXISTS ix_glosa_data_inicio ON glosa_chamados (tenant_id, data_inicio DESC)"),
    ("RLS glosa_chamados",
     "ALTER TABLE glosa_chamados ENABLE ROW LEVEL SECURITY"),
    ("POLICY glosa_tenant_isolation",
     "CREATE POLICY glosa_tenant_isolation ON glosa_chamados USING (tenant_id::text = current_setting('app.current_tenant_id', true))"),

    # ── 3. Tabela glosa_faixas ───────────────────────────────────────────────
    ("CREATE glosa_faixas", """
        CREATE TABLE IF NOT EXISTS glosa_faixas (
            id          SERIAL PRIMARY KEY,
            tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            horas_min   NUMERIC(8,2) NOT NULL,
            horas_max   NUMERIC(8,2),
            percentual  NUMERIC(5,2) NOT NULL CHECK (percentual > 0 AND percentual <= 100),
            ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_glosa_faixas_tenant_min UNIQUE (tenant_id, horas_min)
        )
    """),
    ("INDEX ix_glosa_faixas_tenant",
     "CREATE INDEX IF NOT EXISTS ix_glosa_faixas_tenant ON glosa_faixas (tenant_id, horas_min)"),
    ("RLS glosa_faixas",
     "ALTER TABLE glosa_faixas ENABLE ROW LEVEL SECURITY"),
    ("POLICY glosa_faixas_tenant_isolation",
     "CREATE POLICY glosa_faixas_tenant_isolation ON glosa_faixas USING (tenant_id::text = current_setting('app.current_tenant_id', true))"),

    # ── 4. Seed faixas Polsec ────────────────────────────────────────────────
    ("SEED faixas Polsec", """
        INSERT INTO glosa_faixas (tenant_id, horas_min, horas_max, percentual, ativo) VALUES
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',  1,  24,  2, TRUE),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 24,  60,  4, TRUE),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 60, 168,  8, TRUE),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',168, 240, 16, TRUE),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',240, NULL,32, TRUE)
        ON CONFLICT (tenant_id, horas_min) DO NOTHING
    """),
    ("DEFAULT ativo", """
        ALTER TABLE glosa_faixas ALTER COLUMN ativo SET DEFAULT TRUE
    """),
]

print("=" * 55)
print("POLSEC — Migration 003: Módulo de Glosa")
print("=" * 55)

erros = 0
# AUTOCOMMIT é necessário para DDL (ALTER TABLE / CREATE TABLE) sem deadlock com o app em execução
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    for nome, sql in STATEMENTS:
        try:
            conn.execute(text(sql))
            print(f"  [OK] {nome}")
        except Exception as e:
            msg = str(e).strip().splitlines()[0]
            if "already exists" in msg or "duplicate" in msg.lower() or "AlreadyExists" in type(e).__name__:
                print(f"  [--] {nome} (já existe)")
            else:
                print(f"  [ERRO] {nome}: {msg}")
                erros += 1

print()
if erros == 0:
    print("✓ Migration aplicada com sucesso!")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        qtd = conn.execute(text(
            "SELECT COUNT(*) FROM glosa_faixas WHERE tenant_id = 'dd3ce17e-b506-46cf-9cce-707b20d1e253'"
        )).scalar()
        colunas = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='chamados' AND column_name IN "
            "('numero_chamado','tipo_chamado','data_chegada_tecnico','justificativa_atraso','codigo_unidade') "
            "ORDER BY column_name"
        )).fetchall()
    print(f"  Faixas Polsec: {qtd}")
    print(f"  Colunas novas: {[r[0] for r in colunas]}")
else:
    print(f"✗ {erros} erro(s) — verifique acima.")
    sys.exit(1)


# Lê DATABASE_URL do .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
db_url = ""
with open(env_path) as f:
    for line in f:
        if line.startswith("DATABASE_URL="):
            db_url = line.strip().split("=", 1)[1]
            break

if not db_url:
    print("ERRO: DATABASE_URL não encontrada no .env")
    sys.exit(1)

# Converte SQLAlchemy URL para psycopg
db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
parsed = urlparse(db_url)
conn_params = {
    "host":     parsed.hostname,
    "port":     parsed.port or 5432,
    "dbname":   parsed.path.lstrip("/"),
    "user":     unquote(parsed.username),
    "password": unquote(parsed.password),
    "connect_timeout": 30,
    "options":  "-c statement_timeout=60000",   # 60s por statement
}

import psycopg2

BLOCOS = [
    (
        "Bloco 1 — Novos campos na tabela chamados",
        """
        ALTER TABLE chamados
            ADD COLUMN IF NOT EXISTS numero_chamado       INTEGER,
            ADD COLUMN IF NOT EXISTS tipo_chamado         VARCHAR(20)
                                         CHECK (tipo_chamado IN ('preventiva', 'corretiva')),
            ADD COLUMN IF NOT EXISTS data_chegada_tecnico TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS justificativa_atraso TEXT,
            ADD COLUMN IF NOT EXISTS codigo_unidade       VARCHAR(10)
        """,
    ),
    (
        "Bloco 2a — CREATE TABLE glosa_chamados",
        """
        CREATE TABLE IF NOT EXISTS glosa_chamados (
            id                  SERIAL PRIMARY KEY,
            tenant_id           UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            chamado_id          INTEGER      REFERENCES chamados(id) ON DELETE SET NULL,
            filial_id           INTEGER      REFERENCES filiais(id) ON DELETE SET NULL,
            filial_nome         VARCHAR(150) NOT NULL,
            data_inicio         TIMESTAMPTZ  NOT NULL,
            data_fim            TIMESTAMPTZ,
            horas_indisponiveis NUMERIC(8,2),
            percentual_glosa    NUMERIC(5,2),
            valor_base          NUMERIC(12,2),
            valor_glosa         NUMERIC(12,2),
            status              VARCHAR(20)  NOT NULL DEFAULT 'ativa'
                                    CHECK (status IN ('ativa', 'encerrada', 'contestada', 'cancelada')),
            observacoes         TEXT,
            motivo              TEXT,
            registrado_por_id   INTEGER      REFERENCES funcionarios(id) ON DELETE SET NULL,
            encerrado_por_id    INTEGER      REFERENCES funcionarios(id) ON DELETE SET NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """,
    ),
    (
        "Bloco 2b — Índices glosa_chamados",
        """
        CREATE INDEX IF NOT EXISTS ix_glosa_tenant_status  ON glosa_chamados (tenant_id, status);
        CREATE INDEX IF NOT EXISTS ix_glosa_filial          ON glosa_chamados (filial_id);
        CREATE INDEX IF NOT EXISTS ix_glosa_chamado         ON glosa_chamados (chamado_id);
        CREATE INDEX IF NOT EXISTS ix_glosa_data_inicio     ON glosa_chamados (tenant_id, data_inicio DESC)
        """,
    ),
    (
        "Bloco 2c — RLS glosa_chamados",
        """
        ALTER TABLE glosa_chamados ENABLE ROW LEVEL SECURITY
        """,
    ),
    (
        "Bloco 2d — Policy glosa_chamados",
        """
        CREATE POLICY glosa_tenant_isolation ON glosa_chamados
            USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        """,
    ),
    (
        "Bloco 3a — CREATE TABLE glosa_faixas",
        """
        CREATE TABLE IF NOT EXISTS glosa_faixas (
            id          SERIAL PRIMARY KEY,
            tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            horas_min   NUMERIC(8,2) NOT NULL,
            horas_max   NUMERIC(8,2),
            percentual  NUMERIC(5,2) NOT NULL CHECK (percentual > 0 AND percentual <= 100),
            ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_glosa_faixas_tenant_min UNIQUE (tenant_id, horas_min)
        )
        """,
    ),
    (
        "Bloco 3b — Índice + RLS glosa_faixas",
        """
        CREATE INDEX IF NOT EXISTS ix_glosa_faixas_tenant ON glosa_faixas (tenant_id, horas_min)
        """,
    ),
    (
        "Bloco 3c — RLS glosa_faixas",
        """
        ALTER TABLE glosa_faixas ENABLE ROW LEVEL SECURITY
        """,
    ),
    (
        "Bloco 3d — Policy glosa_faixas",
        """
        CREATE POLICY glosa_faixas_tenant_isolation ON glosa_faixas
            USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        """,
    ),
    (
        "Bloco 4 — Seed faixas padrão Polsec",
        """
        INSERT INTO glosa_faixas (tenant_id, horas_min, horas_max, percentual) VALUES
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',   1,   24,  2),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',  24,   60,  4),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253',  60,  168,  8),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 168,  240, 16),
            ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 240, NULL, 32)
        ON CONFLICT (tenant_id, horas_min) DO NOTHING
        """,
    ),
]

print("=" * 60)
print("POLSEC — Migration 003: Módulo de Glosa")
print(f"Host: {conn_params['host']}")
print("=" * 60)

try:
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
except Exception as e:
    print(f"ERRO de conexão: {e}")
    sys.exit(1)

erros = 0
for nome, sql in BLOCOS:
    try:
        cur.execute(sql.strip())
        print(f"  [OK] {nome}")
    except psycopg2.errors.DuplicateObject as e:
        print(f"  [OK] {nome} (já existe, ignorado)")
    except Exception as e:
        msg = str(e).strip().splitlines()[0]
        print(f"  [ERRO] {nome}: {msg}")
        erros += 1

cur.close()
conn.close()

print()
if erros == 0:
    print("✓ Migration aplicada com sucesso!")
    # Verifica resultado
    conn2 = psycopg2.connect(**conn_params)
    cur2 = conn2.cursor()
    cur2.execute("SELECT COUNT(*) FROM glosa_faixas WHERE tenant_id = 'dd3ce17e-b506-46cf-9cce-707b20d1e253'")
    qtd = cur2.fetchone()[0]
    cur2.execute("SELECT column_name FROM information_schema.columns WHERE table_name='chamados' AND column_name IN ('numero_chamado','tipo_chamado','data_chegada_tecnico','justificativa_atraso','codigo_unidade') ORDER BY column_name")
    colunas = [r[0] for r in cur2.fetchall()]
    cur2.close()
    conn2.close()
    print(f"  Faixas inseridas:  {qtd}")
    print(f"  Colunas em chamados: {colunas}")
else:
    print(f"✗ {erros} erro(s) — verifique acima.")
    sys.exit(1)

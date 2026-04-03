-- ============================================================
-- POLSEC — Schema Multitenant com Row Level Security (RLS)
-- Execute este arquivo no SQL Editor do Supabase
-- ============================================================

-- ── Extensões ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tabela: tenants ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        VARCHAR(100) UNIQUE NOT NULL,
    nome        VARCHAR(200) NOT NULL,
    email_admin VARCHAR(150) NOT NULL,
    plano       VARCHAR(50)  NOT NULL DEFAULT 'basico',
    ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
    logo_url    VARCHAR(500),
    configuracoes TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Tabela: usuarios ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id           SERIAL PRIMARY KEY,
    supabase_uid UUID UNIQUE NOT NULL,           -- auth.users.id
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    nome         VARCHAR(150) NOT NULL,
    email        VARCHAR(150) NOT NULL,
    perfil       VARCHAR(50)  NOT NULL DEFAULT 'operador',  -- admin | gestor | operador | auditor
    ativo        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, email)
);

-- ── Tabela: patrimonios ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS patrimonios (
    id              SERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    codigo          VARCHAR(50) NOT NULL,
    descricao       VARCHAR(300) NOT NULL,
    categoria       VARCHAR(100),
    setor           VARCHAR(100),
    localizacao     VARCHAR(200),
    responsavel_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'ativo',
    valor           NUMERIC(15,2),
    data_aquisicao  DATE,
    observacoes     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, codigo)
);

-- ── Tabela: movimentacoes ────────────────────────────────────
CREATE TABLE IF NOT EXISTS movimentacoes (
    id              SERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patrimonio_id   INTEGER NOT NULL REFERENCES patrimonios(id) ON DELETE CASCADE,
    tipo            VARCHAR(50) NOT NULL,
    descricao       TEXT,
    dados_anteriores JSONB,
    dados_novos     JSONB,
    usuario_id      INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Tabela: audit_logs ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    usuario_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    acao        VARCHAR(100) NOT NULL,
    tabela      VARCHAR(100) NOT NULL,
    registro_id INTEGER,
    dados       JSONB,
    ip          VARCHAR(45),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Índices ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_usuarios_tenant        ON usuarios(tenant_id);
CREATE INDEX IF NOT EXISTS idx_patrimonios_tenant     ON patrimonios(tenant_id);
CREATE INDEX IF NOT EXISTS idx_patrimonios_status     ON patrimonios(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_tenant   ON movimentacoes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_pat      ON movimentacoes(patrimonio_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant      ON audit_logs(tenant_id);

-- ── Função auxiliar para RLS ──────────────────────────────────
-- Lê app.current_tenant_id da sessão PostgreSQL (set pelo backend)
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', TRUE)::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- ── Habilitar RLS ────────────────────────────────────────────
ALTER TABLE tenants        ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios       ENABLE ROW LEVEL SECURITY;
ALTER TABLE patrimonios    ENABLE ROW LEVEL SECURITY;
ALTER TABLE movimentacoes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs     ENABLE ROW LEVEL SECURITY;

-- ── Políticas RLS — tenants ──────────────────────────────────
-- Apenas o próprio tenant é visível
CREATE POLICY tenant_isolation ON tenants
    USING (id = current_tenant_id());

-- ── Políticas RLS — usuarios ─────────────────────────────────
CREATE POLICY tenant_isolation ON usuarios
    USING (tenant_id = current_tenant_id());

-- ── Políticas RLS — patrimonios ──────────────────────────────
CREATE POLICY tenant_isolation ON patrimonios
    USING (tenant_id = current_tenant_id());

-- ── Políticas RLS — movimentacoes ────────────────────────────
CREATE POLICY tenant_isolation ON movimentacoes
    USING (tenant_id = current_tenant_id());

-- ── Políticas RLS — audit_logs ───────────────────────────────
CREATE POLICY tenant_isolation ON audit_logs
    USING (tenant_id = current_tenant_id());

-- ── Trigger: updated_at automático ───────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_patrimonios_updated_at
    BEFORE UPDATE ON patrimonios
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Permissões para o service role (bypass RLS quando necessário) ──────────
-- O service_role do Supabase já bypassa RLS por padrão.
-- O anon/authenticated role usa RLS acima.

-- ── Comentários ─────────────────────────────────────────────
COMMENT ON TABLE tenants IS 'Empresas cadastradas no SaaS POLSEC';
COMMENT ON TABLE usuarios IS 'Usuários vinculados a um tenant; autenticação via Supabase Auth';
COMMENT ON TABLE patrimonios IS 'Acervo patrimonial isolado por tenant';
COMMENT ON TABLE movimentacoes IS 'Histórico de movimentações de patrimônios';
COMMENT ON TABLE audit_logs IS 'Log de auditoria de todas as operações';
COMMENT ON FUNCTION current_tenant_id IS 'Lê o tenant ativo da variável de sessão app.current_tenant_id';

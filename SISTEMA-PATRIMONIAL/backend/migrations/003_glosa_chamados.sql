-- ============================================================
-- POLSEC — Migração: Módulo de Glosa e Campos SLA de Chamados
-- EXECUTE UM BLOCO POR VEZ no SQL Editor do Supabase
-- ============================================================


-- ════════════════════════════════════════════════════════════
-- BLOCO 1 de 4 — Novos campos na tabela chamados
-- Cole e execute este bloco primeiro.
-- ════════════════════════════════════════════════════════════

ALTER TABLE chamados
    ADD COLUMN IF NOT EXISTS numero_chamado       INTEGER,
    ADD COLUMN IF NOT EXISTS tipo_chamado         VARCHAR(20)
                                 CHECK (tipo_chamado IN ('preventiva', 'corretiva')),
    ADD COLUMN IF NOT EXISTS data_chegada_tecnico TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS justificativa_atraso TEXT,
    ADD COLUMN IF NOT EXISTS codigo_unidade       VARCHAR(10);


-- ════════════════════════════════════════════════════════════
-- BLOCO 2 de 4 — Tabela glosa_chamados
-- Cole e execute após o Bloco 1.
-- ════════════════════════════════════════════════════════════

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
);

CREATE INDEX IF NOT EXISTS ix_glosa_tenant_status  ON glosa_chamados (tenant_id, status);
CREATE INDEX IF NOT EXISTS ix_glosa_filial          ON glosa_chamados (filial_id);
CREATE INDEX IF NOT EXISTS ix_glosa_chamado         ON glosa_chamados (chamado_id);
CREATE INDEX IF NOT EXISTS ix_glosa_data_inicio     ON glosa_chamados (tenant_id, data_inicio DESC);

ALTER TABLE glosa_chamados ENABLE ROW LEVEL SECURITY;

CREATE POLICY glosa_tenant_isolation ON glosa_chamados
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));


-- ════════════════════════════════════════════════════════════
-- BLOCO 3 de 4 — Tabela glosa_faixas
-- Cole e execute após o Bloco 2.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS glosa_faixas (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    horas_min   NUMERIC(8,2) NOT NULL,
    horas_max   NUMERIC(8,2),
    percentual  NUMERIC(5,2) NOT NULL CHECK (percentual > 0 AND percentual <= 100),
    ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_glosa_faixas_tenant_min UNIQUE (tenant_id, horas_min)
);

CREATE INDEX IF NOT EXISTS ix_glosa_faixas_tenant ON glosa_faixas (tenant_id, horas_min);

ALTER TABLE glosa_faixas ENABLE ROW LEVEL SECURITY;

CREATE POLICY glosa_faixas_tenant_isolation ON glosa_faixas
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));


-- ════════════════════════════════════════════════════════════
-- BLOCO 4 de 4 — Seed faixas padrão Polsec
-- Cole e execute após o Bloco 3.
-- (Pode pular este bloco e usar o botão na tela /admin/glosa/faixas/config)
-- ════════════════════════════════════════════════════════════

INSERT INTO glosa_faixas (tenant_id, horas_min, horas_max, percentual) VALUES
    ('dd3ce17e-b506-46cf-9cce-707b20d1e253',   1,   24,  2),
    ('dd3ce17e-b506-46cf-9cce-707b20d1e253',  24,   60,  4),
    ('dd3ce17e-b506-46cf-9cce-707b20d1e253',  60,  168,  8),
    ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 168,  240, 16),
    ('dd3ce17e-b506-46cf-9cce-707b20d1e253', 240, NULL, 32)
ON CONFLICT (tenant_id, horas_min) DO NOTHING;

-- ============================================================
-- POLSEC — Migração: Histórico de Faturamento por Unidade
-- Execute no SQL Editor do Supabase (porta 5432 / session mode)
-- ============================================================

CREATE TABLE IF NOT EXISTS faturamento_historico (
    id              SERIAL PRIMARY KEY,
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Vínculo com a filial (pode ser NULL para unidades não cadastradas)
    filial_id       INTEGER     REFERENCES filiais(id) ON DELETE SET NULL,
    -- Nome snapshot — preservado independente de renomeações futuras
    filial_nome     VARCHAR(150) NOT NULL,

    mes             SMALLINT    NOT NULL CHECK (mes BETWEEN 1 AND 12),
    ano             SMALLINT    NOT NULL CHECK (ano >= 2020),

    chamados_count  INTEGER     NOT NULL DEFAULT 0,
    valor_mao_obra  NUMERIC(12,2) NOT NULL DEFAULT 0,
    valor_pecas     NUMERIC(12,2) NOT NULL DEFAULT 0,
    valor_total     NUMERIC(12,2) NOT NULL,

    observacoes     TEXT,
    origem          VARCHAR(20)  NOT NULL DEFAULT 'sistema'
                        CHECK (origem IN ('sistema', 'importacao')),
    arquivo_origem  VARCHAR(255),          -- nome do xlsx importado (quando origem='importacao')

    fechado_por_id  INTEGER     REFERENCES funcionarios(id) ON DELETE SET NULL,
    fechado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unicidade: evita duplicar o mesmo período/unidade/origem
    CONSTRAINT uq_fat_hist_unidade_periodo
        UNIQUE (tenant_id, filial_nome, mes, ano, origem)
);

-- Índices de desempenho
CREATE INDEX IF NOT EXISTS ix_fat_hist_tenant_periodo
    ON faturamento_historico (tenant_id, ano DESC, mes DESC);

CREATE INDEX IF NOT EXISTS ix_fat_hist_filial
    ON faturamento_historico (filial_id);

-- RLS (Row Level Security) — mesmo padrão do restante do schema
ALTER TABLE faturamento_historico ENABLE ROW LEVEL SECURITY;

CREATE POLICY fat_hist_tenant_isolation ON faturamento_historico
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

-- Comentários descritivos
COMMENT ON TABLE faturamento_historico IS
    'Snapshots fechados de faturamento por unidade e período mensal. '
    'Origem "sistema" = gerado pelo admin a partir dos chamados/orçamentos. '
    'Origem "importacao" = importado de planilha Excel externa (dados históricos).';

-- ============================================================
-- POLSEC — Migração 004: Controle de Gasto com Diesel
-- Execute no SQL Editor do Supabase ou via script Python
-- ============================================================

CREATE TABLE IF NOT EXISTS gastos_diesel (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    data        TIMESTAMPTZ  NOT NULL,
    numero_nota INTEGER,
    descricao   VARCHAR(300) NOT NULL,
    local       VARCHAR(150),
    tecnico     VARCHAR(150),
    litros      NUMERIC(10,3),
    valor_litro NUMERIC(8,3),
    valor_total NUMERIC(12,2) NOT NULL,
    observacoes TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_diesel_tenant_data ON gastos_diesel (tenant_id, data DESC);
CREATE INDEX IF NOT EXISTS ix_diesel_local       ON gastos_diesel (tenant_id, local);

ALTER TABLE gastos_diesel ENABLE ROW LEVEL SECURITY;

CREATE POLICY diesel_tenant_isolation ON gastos_diesel
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

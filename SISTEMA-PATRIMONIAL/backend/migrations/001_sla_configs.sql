-- ============================================================
-- Migração 001 — Configurações de SLA por tenant + prioridade
-- ============================================================

CREATE TABLE IF NOT EXISTS sla_configs (
    id                   SERIAL PRIMARY KEY,
    tenant_id            VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    prioridade           VARCHAR(20) NOT NULL,          -- baixa | media | alta | critica
    prazo_resposta_horas  FLOAT       NOT NULL,
    prazo_resolucao_horas FLOAT       NOT NULL,
    ativo                BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sla_tenant_prioridade UNIQUE (tenant_id, prioridade)
);

-- Índice para consultas por tenant
CREATE INDEX IF NOT EXISTS idx_sla_configs_tenant_id ON sla_configs(tenant_id);

-- Seed: SLAs padrão para o tenant POLSEC
-- Substitua o UUID abaixo pelo id real do tenant caso necessário.
-- O seed_sla_padrao() no sla_service.py também cria esses registros via ORM.
/*
INSERT INTO sla_configs (tenant_id, prioridade, prazo_resposta_horas, prazo_resolucao_horas)
SELECT t.id, v.prioridade, v.resposta, v.resolucao
FROM tenants t
CROSS JOIN (VALUES
    ('critica', 1.0,  4.0),
    ('alta',    4.0, 24.0),
    ('media',   8.0, 48.0),
    ('baixa',  24.0, 96.0)
) AS v(prioridade, resposta, resolucao)
ON CONFLICT (tenant_id, prioridade) DO NOTHING;
*/

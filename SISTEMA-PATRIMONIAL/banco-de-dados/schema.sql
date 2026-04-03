-- ============================================================
-- Schema do Banco de Dados — Sistema Patrimonial EMTEL
-- Banco: PostgreSQL
-- Data: 02/04/2026
-- ============================================================

CREATE DATABASE emtel_patrimonial
  ENCODING = 'UTF8'
  LC_COLLATE = 'pt_BR.UTF-8'
  LC_CTYPE = 'pt_BR.UTF-8';

\c emtel_patrimonial;

-- Tipos ENUM
CREATE TYPE perfil_usuario AS ENUM ('administrador', 'operador', 'visualizador');
CREATE TYPE status_patrimonio AS ENUM ('ativo', 'manutencao', 'baixado', 'extraviado');
CREATE TYPE tipo_movimentacao AS ENUM (
  'transferencia_setor',
  'troca_responsavel',
  'mudanca_status',
  'edicao_dados'
);

-- ============================================================
-- TABELA: usuarios
-- ============================================================
CREATE TABLE usuarios (
  id          SERIAL PRIMARY KEY,
  nome        VARCHAR(150)    NOT NULL,
  email       VARCHAR(150)    NOT NULL UNIQUE,
  senha_hash  VARCHAR(255)    NOT NULL,
  perfil      perfil_usuario  NOT NULL DEFAULT 'operador',
  ativo       BOOLEAN         NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usuarios_email ON usuarios(email);

-- ============================================================
-- TABELA: patrimonios
-- ============================================================
CREATE TABLE patrimonios (
  id              SERIAL PRIMARY KEY,
  codigo          VARCHAR(50)        NOT NULL UNIQUE,
  descricao       VARCHAR(255)       NOT NULL,
  categoria       VARCHAR(100)       NOT NULL,
  setor           VARCHAR(100)       NOT NULL,
  localizacao     VARCHAR(150),
  responsavel_id  INTEGER            REFERENCES usuarios(id) ON DELETE SET NULL,
  data_aquisicao  TIMESTAMP,
  valor           NUMERIC(12, 2),
  status          status_patrimonio  NOT NULL DEFAULT 'ativo',
  observacoes     TEXT,
  created_at      TIMESTAMP          NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMP          NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patrimonios_codigo   ON patrimonios(codigo);
CREATE INDEX idx_patrimonios_setor    ON patrimonios(setor);
CREATE INDEX idx_patrimonios_status   ON patrimonios(status);
CREATE INDEX idx_patrimonios_responsavel ON patrimonios(responsavel_id);

-- ============================================================
-- TABELA: movimentacoes
-- ============================================================
CREATE TABLE movimentacoes (
  id                SERIAL PRIMARY KEY,
  patrimonio_id     INTEGER           NOT NULL REFERENCES patrimonios(id) ON DELETE CASCADE,
  tipo              tipo_movimentacao NOT NULL,
  descricao         TEXT,
  dados_anteriores  JSONB,
  dados_novos       JSONB,
  usuario_id        INTEGER           NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
  created_at        TIMESTAMP         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_movimentacoes_patrimonio ON movimentacoes(patrimonio_id);
CREATE INDEX idx_movimentacoes_usuario    ON movimentacoes(usuario_id);
CREATE INDEX idx_movimentacoes_data       ON movimentacoes(created_at DESC);

-- ============================================================
-- TABELA: audit_logs
-- ============================================================
CREATE TABLE audit_logs (
  id           SERIAL PRIMARY KEY,
  usuario_id   INTEGER      REFERENCES usuarios(id) ON DELETE SET NULL,
  acao         VARCHAR(100) NOT NULL,
  tabela       VARCHAR(100) NOT NULL,
  registro_id  INTEGER,
  dados        JSONB,
  ip           VARCHAR(45),
  created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_usuario    ON audit_logs(usuario_id);
CREATE INDEX idx_audit_logs_tabela     ON audit_logs(tabela, registro_id);
CREATE INDEX idx_audit_logs_data       ON audit_logs(created_at DESC);

-- ============================================================
-- TRIGGER: atualiza updated_at automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usuarios_updated_at
  BEFORE UPDATE ON usuarios
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_patrimonios_updated_at
  BEFORE UPDATE ON patrimonios
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- DADOS INICIAIS: usuário administrador padrão
-- Senha: emtel@2026 (bcrypt — trocar em produção)
-- ============================================================
INSERT INTO usuarios (nome, email, senha_hash, perfil)
VALUES (
  'Administrador',
  'admin@emtel.com.br',
  '$2b$12$PlaceholderHashTrocarEmProducaoXXXXXXXXXXXXXXXXXXXXX',
  'administrador'
);

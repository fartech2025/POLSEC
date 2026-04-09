.PHONY: dev build up down logs shell test lint migrate seed help

# ── Variáveis ──────────────────────────────────────────────────────────────────
PYTHON := .venv/bin/python3
PIP    := .venv/bin/pip

# ── Desenvolvimento local ──────────────────────────────────────────────────────

## Instala dependências no venv (cria se não existir)
install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

## Inicia servidor em modo desenvolvimento (hot-reload)
dev:
	$(PYTHON) run.py

## Inicia via Docker Compose
up:
	docker compose up --build

## Para containers
down:
	docker compose down

## Logs do container em tempo real
logs:
	docker compose logs -f api

## Shell dentro do container
shell:
	docker compose exec api /bin/bash

# ── Build de produção ──────────────────────────────────────────────────────────

## Build da imagem Docker de produção
build:
	docker build --target runtime -t polsec-api:latest .

# ── Banco de dados ─────────────────────────────────────────────────────────────

## Aplica migrations SQL pendentes (executa todos em migrations/)
migrate:
	$(PYTHON) -c "\
from app.database import engine; \
from sqlalchemy import text; \
import glob, os; \
files = sorted(glob.glob('migrations/*.sql')); \
conn = engine.connect().execution_options(isolation_level='AUTOCOMMIT'); \
[conn.execute(text(open(f).read())) or print(f'✓ {os.path.basename(f)}') for f in files]; \
conn.close(); print('Migrations aplicadas.')"

## Popula SLA padrão
seed:
	$(PYTHON) seed_sla.py

## Cria usuários de teste (POLSEC)
seed-users:
	$(PYTHON) criar_usuarios_teste.py

# ── Qualidade de código ────────────────────────────────────────────────────────

## Checa formatação e tipagem (requer ruff e mypy)
lint:
	.venv/bin/ruff check app/ || true
	.venv/bin/mypy app/ --ignore-missing-imports || true

# ── Segurança ──────────────────────────────────────────────────────────────────

## Gera nova SECRET_KEY (Fernet)
gen-key:
	$(PYTHON) -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

## Executa auditoria de segurança manual
audit:
	$(PYTHON) -m app.security.audit

# ── Ajuda ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Comandos disponíveis:"
	@echo "  make install      — Cria venv e instala dependências"
	@echo "  make dev          — Servidor local com hot-reload"
	@echo "  make up           — Sobe via Docker Compose"
	@echo "  make build        — Build imagem de produção"
	@echo "  make migrate      — Aplica migrations SQL"
	@echo "  make seed         — Seed de SLAs padrão"
	@echo "  make gen-key      — Gera SECRET_KEY Fernet"
	@echo "  make audit        — Auditoria de segurança"
	@echo ""

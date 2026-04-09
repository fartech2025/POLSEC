# POLSEC — Sistema de Gestão Patrimonial

> Sistema web multi-tenant para controle de patrimônio, chamados técnicos, gestão de glosas, consumo de diesel e faturamento. Desenvolvido para o **Grupo EMTEL**.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI 0.111 · SQLAlchemy 2.0 |
| Banco de dados | PostgreSQL 17 (Supabase) |
| Autenticação | JWT (Supabase Auth) |
| Frontend | Jinja2 · Tailwind CSS · PWA |
| IA | Anthropic Claude (Assistente) |
| Container | Docker · Docker Compose |

---

## Módulos

| Módulo | Descrição |
|---|---|
| **Patrimônio** | Cadastro, movimentação e rastreio de ativos |
| **Chamados** | Abertura, acompanhamento e SLA de chamados técnicos |
| **Análise SLA** | Relatório de chamados abertos × meta de atendimento |
| **Glosa** | Gestão e contestação de glosas de faturamento |
| **Diesel** | Controle de abastecimento por veículo e filial |
| **Faturamento** | Histórico e DRE simplificado por empresa |
| **Assistente IA** | Chat com Claude para consultas sobre o sistema |
| **Superadmin** | Gestão de tenants e usuários (Fartech) |

---

## Requisitos

- Python 3.12+
- Docker 24+ e Docker Compose v2 (para execução em container)
- Conta no [Supabase](https://supabase.com) com projeto ativo

---

## Configuração rápida (local)

### 1. Clone e venv

```bash
git clone https://github.com/fartech2025/POLSEC.git
cd POLSEC/SISTEMA-PATRIMONIAL/backend

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` com as credenciais do seu projeto Supabase:

```env
DEBUG=true
DATABASE_URL=postgresql+psycopg://postgres.<project-id>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
ANTHROPIC_API_KEY=...
SECRET_KEY=<fernet-key>           # make gen-key
```

### 3. Banco de dados

Aplique o schema principal no painel SQL do Supabase:

```bash
# Cole o conteúdo de supabase_schema.sql no SQL Editor do Supabase, ou:
psql $DATABASE_URL -f supabase_schema.sql
```

Migrations incrementais:

```bash
make migrate    # aplica migrations/001_*.sql … migrations/004_*.sql
make seed       # popula SLAs padrão
```

### 4. Iniciar

```bash
make dev        # hot-reload em http://localhost:8000
```

---

## Docker (recomendado para produção)

```bash
# Desenvolvimento com hot-reload
make up

# Build da imagem de produção
make build
docker run --env-file .env -p 8000:8000 polsec-api:latest
```

O `Dockerfile` usa build multi-estágio:
- **builder** — instala dependências com pip wheel
- **runtime** — imagem slim sem compiladores, usuário não-root `app:app`

Health check disponível em `GET /health`.

---

## Comandos úteis (`make help`)

```
make install      — Cria venv e instala dependências
make dev          — Servidor local com hot-reload
make up           — Sobe via Docker Compose
make build        — Build imagem de produção
make migrate      — Aplica migrations SQL
make seed         — Seed de SLAs padrão
make gen-key      — Gera SECRET_KEY Fernet
make audit        — Auditoria de segurança
```

---

## Estrutura do projeto

```
backend/
├── app/
│   ├── main.py            # App FastAPI, middlewares, routers
│   ├── config.py          # Settings (pydantic-settings)
│   ├── database.py        # Engine SQLAlchemy
│   ├── models/            # ORM models
│   ├── routers/           # Endpoints por domínio
│   ├── schemas/           # Pydantic schemas (request/response)
│   ├── services/          # Lógica de negócio
│   ├── middleware/        # Rate limit, security headers, tenant
│   ├── security/          # Auditoria de segurança
│   ├── templates/         # Jinja2 HTML
│   └── static/            # CSS, JS, PWA manifest
├── migrations/            # SQL incrementais (001…004)
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── run.py                 # Entrypoint local
└── .env.example
```

---

## Segurança

- Credenciais **nunca** commitadas — apenas `.env.example` no repositório
- Headers de segurança via `SecurityHeadersMiddleware` (CSP, HSTS, X-Frame-Options, …)
- Rate limiting no endpoint de login (`LoginRateLimitMiddleware`)
- Isolamento multi-tenant via `TenantMiddleware`
- Auditoria de segurança diária agendada (2h00)
- Docs Swagger/ReDoc desabilitados em produção (`DEBUG=false`)

---

## Licença

Proprietário — Fartech / Grupo EMTEL. Todos os direitos reservados.

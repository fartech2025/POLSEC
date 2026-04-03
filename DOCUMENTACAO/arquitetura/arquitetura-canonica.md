# Arquitetura Canônica — Sistema Patrimonial POLSEC/FARTECH

> **Versão:** 3.0  
> **Data:** 03/04/2026  
> **Commit HEAD:** `beca4ab`  
> **Branch:** `main`

---

## 1. Visão Geral

O **Sistema Patrimonial** é uma aplicação web multi-tenant SaaS desenvolvida pela FARTECH para gerenciamento de bens patrimoniais, chamados de manutenção e controle de SLA. Cada empresa contratante (ex.: POLSEC) opera em seu próprio tenant isolado.

```
Navegador
   │  HTTPS
   ▼
FastAPI 0.111 (uvicorn, porta 8000)
   │  SQLAlchemy 2.0
   ▼
Supabase PostgreSQL 17.6
   │  Supabase Auth (ES256 JWKS)
   ▼
Anthropic Claude (Assistente IA)
```

---

## 2. Stack Tecnológica

| Camada | Tecnologia | Versão |
|---|---|---|
| Runtime | Python | 3.12 |
| Web framework | FastAPI | 0.111 |
| Servidor ASGI | Uvicorn + WatchFiles | — |
| ORM | SQLAlchemy | 2.0 |
| Banco de dados | Supabase PostgreSQL | 17.6 |
| Autenticação | Supabase Auth (ES256 JWT via JWKS) | — |
| Templates | Jinja2 | — |
| CSS framework | Bootstrap 5 + Bootstrap Icons | — |
| Fonte | Barlow (Google Fonts) / Helixa | — |
| IA | Anthropic Claude | API |
| Validação settings | pydantic-settings | — |

---

## 3. Estrutura de Diretórios

```
backend/
├── run.py                        # Entry point: uvicorn com reload
├── seed_sla.py                   # Migração + seed dos SLAs padrão
├── criar_usuarios_teste.py       # Script de seed de usuários de teste
├── requirements.txt
├── migrations/
│   └── 001_sla_configs.sql       # DDL da tabela sla_configs
├── app/
│   ├── main.py                   # Criação do app FastAPI, routers, middleware
│   ├── config.py                 # Settings via pydantic-settings (.env)
│   ├── database.py               # Engine SQLAlchemy, SessionLocal, Base
│   ├── middleware/
│   │   └── tenant.py             # TenantMiddleware — injeta tenant no request
│   ├── models/                   # ORM models (SQLAlchemy Declarative)
│   │   ├── tenant.py
│   │   ├── usuario.py            # PerfilUsuario enum: superadmin|administrador|operador|visualizador
│   │   ├── patrimonio.py
│   │   ├── movimentacao.py
│   │   ├── audit_log.py
│   │   ├── cargo.py
│   │   ├── filial.py
│   │   ├── funcionario.py
│   │   ├── chamado.py            # PrioridadeChamado + StatusChamado enums
│   │   ├── peca.py
│   │   ├── orcamento.py
│   │   └── sla.py                # SLAConfig — prazos por tenant + prioridade
│   ├── routers/                  # Handlers HTTP por domínio
│   │   ├── auth.py               # Login/logout (Supabase + cookie httponly)
│   │   ├── dashboard.py          # Redireciona por perfil
│   │   ├── superadmin.py         # Interface FARTECH (gestão de tenants)
│   │   ├── admin.py              # Interface Administrador POLSEC
│   │   ├── tecnico.py            # Interface Técnico (perfil operador)
│   │   ├── patrimonio.py
│   │   ├── movimentacao.py
│   │   ├── chamado.py            # API REST de chamados
│   │   ├── cargo.py
│   │   ├── filial.py
│   │   ├── funcionario.py
│   │   ├── peca.py
│   │   ├── orcamento.py
│   │   ├── assistente.py         # Chat IA (Anthropic Claude)
│   │   ├── da.py                 # Data Analytics
│   │   └── tenant.py             # Auto-registro de empresa
│   ├── services/
│   │   ├── auth_service.py       # Verificação JWT ES256 via JWKS, get_usuario_logado
│   │   ├── chamado_service.py    # Lógica de negócio de chamados
│   │   ├── sla_service.py        # Cálculo de SLA em lote, seed de prazos padrão
│   │   ├── patrimonio_service.py
│   │   ├── tenant_service.py
│   │   ├── da_service.py
│   │   ├── llm_service.py        # Integração Anthropic Claude
│   │   ├── rbac_service.py       # RBAC helper
│   │   └── storage_service.py    # Supabase Storage
│   ├── schemas/                  # Pydantic schemas (validação de entrada)
│   │   ├── patrimonio.py
│   │   ├── movimentacao.py
│   │   └── usuario.py
│   ├── templates/                # Jinja2 HTML
│   │   ├── base.html             # Layout admin/geral (POLSEC azul)
│   │   ├── base_tecnico.html     # Layout painel técnico
│   │   ├── base_superadmin.html  # Layout FARTECH (dark)
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── admin/
│   │   │   ├── chamados.html
│   │   │   ├── funcionarios.html
│   │   │   ├── usuarios.html
│   │   │   └── sla.html          # Configuração de SLA por prioridade
│   │   ├── tecnico/
│   │   │   ├── painel.html       # Lista de chamados com badges SLA
│   │   │   ├── chamado.html      # Detalhe/atualização de chamado
│   │   │   └── novo_chamado.html # (legado — substituído por modal no painel)
│   │   ├── superadmin/
│   │   │   ├── dashboard.html
│   │   │   └── tenants.html
│   │   ├── patrimonio/
│   │   ├── movimentacao/
│   │   ├── assistente/
│   │   ├── da/
│   │   └── tenant/
│   └── static/
│       ├── css/style.css
│       └── js/main.js
```

---

## 4. Banco de Dados

### 4.1 Tabelas Principais

| Tabela | Descrição |
|---|---|
| `tenants` | Empresas contratantes (slug único) |
| `usuarios` | Usuários autenticados (vinculados ao Supabase Auth via `supabase_uid`) |
| `patrimonios` | Bens patrimoniais por tenant |
| `movimentacoes` | Histórico de movimentação de bens |
| `audit_logs` | Log de auditoria de operações |
| `cargos` | Cargos por tenant |
| `filiais` | Filiais / unidades por tenant |
| `funcionarios` | RH do tenant (relacionado a `usuario_id`, `cargo_id`, `filial_id`) |
| `chamados` | Ordens de serviço com estado e prioridade |
| `pecas` | Estoque de peças por filial |
| `orcamentos` | Orçamentos vinculados a chamados |
| `sla_configs` | Prazos de SLA por tenant e prioridade (**novo**) |

### 4.2 SLAConfig — Prazos Padrão

| Prioridade | Resposta | Resolução | Caso de uso típico |
|---|---|---|---|
| 🔴 Crítica | 1 h | 4 h | Servidor/sistema fora do ar |
| 🟠 Alta | 4 h | 24 h | Equipamento de produção com falha parcial |
| 🟡 Média | 8 h | 48 h | Impressora com defeito, lentidão |
| 🟢 Baixa | 24 h | 96 h | Ajuste cosmético, melhoria |

### 4.3 Máquina de Estados — Chamado

```
aberto
  │
  ▼
em_atendimento ──► aguardando_peca
  │                      │
  │◄─────────────────────┘
  │
  ▼
aguardando_aprovacao ──► rejeitado
  │
  ▼
concluido
  │   (qualquer estado)
  ▼
cancelado
```

---

## 5. Autenticação e Segurança

### Fluxo de Login

```
POST /auth/login
  │  email + senha → Supabase Auth REST
  │  ← tokens JWT (access + refresh)
  │  Decodifica claims sem verificar assinatura local (já validado pelo Supabase)
  │  Extrai tenant_slug de user_metadata.slug
  │    → se ausente: fallback via supabase_uid → DB → tenants
  │  Seta cookies httponly:
  │    access_token   (1h)
  │    refresh_token  (7d)
  │    tenant_slug    (7d, httponly=False para middleware)
  ▼
GET /dashboard → redireciona por perfil
```

### Verificação JWT por Request

```
TenantMiddleware
  │  Lê cookie tenant_slug → injeta request.state.tenant
  ▼
auth_service.get_usuario_logado()
  │  Lê cookie access_token
  │  Busca JWKS em <SUPABASE_URL>/auth/v1/.well-known/jwks.json (algoritmo ES256)
  │  Verifica assinatura + expiração
  │  Busca Usuario no DB por supabase_uid
  ▼
Dependência FastAPI injetada nos routers
```

### Perfis e Permissões

| Perfil | Acesso |
|---|---|
| `superadmin` | Interface FARTECH (`/superadmin`), pode navegar qualquer interface para suporte |
| `administrador` | Interface POLSEC completa (`/admin`, `/patrimonio`, `/movimentacao`, etc.) |
| `operador` | Painel técnico (`/tecnico`) — gerencia chamados atribuídos |
| `visualizador` | Somente leitura; bloqueado em `/tecnico` |

---

## 6. Interfaces de Usuário

### Bases de Layout

| Base | Tema | Usado por |
|---|---|---|
| `base_superadmin.html` | Dark (`#0a0a0a` + `#1a1a2e`) | Superadmin FARTECH |
| `base.html` | POLSEC azul (`#003366`) | Administrador |
| `base_tecnico.html` | POLSEC azul claro | Técnico (operador) |

### Fluxo de Redirecionamento por Perfil

```
GET /dashboard
  ├── superadmin    → /superadmin
  ├── administrador → /admin/chamados
  ├── operador      → /tecnico
  └── visualizador  → /patrimonio
```

### Painel do Técnico — Destaques

- Tabela de chamados com coluna **SLA** (badge colorido + contador de horas)
- Modal **Novo Chamado** embutido na página (sem navegação)
- Abre via botão no cabeçalho ou link `#novo` na sidebar
- Máquina de estados completa com transições e registro de solução

---

## 7. Sistema de SLA

Implementado em `app/services/sla_service.py`.

### Cálculo

```python
percentual = horas_decorridas / prazo_resolucao_horas * 100
```

| Faixa | Status | Cor Bootstrap |
|---|---|---|
| < 80 % | `no_prazo` | `success` (verde) |
| 80–99 % | `atencao` | `warning` (amarelo) |
| ≥ 100 % (aberto) | `violado` | `danger` (vermelho) |
| Concluído dentro | `concluido_ok` | `success` |
| Concluído fora | `concluido_violado` | `danger` |
| Sem config | `sem_sla` | `secondary` |

### Performance

`calcular_sla_lote()` carrega todas as configs do tenant em **1 query** antes de iterar os chamados (sem N+1).

### Configuração pelo Admin

`GET/POST /admin/sla` — formulário para editar prazos de resposta e resolução por prioridade.  
`POST /admin/sla/resetar` — remove customizações, volta aos padrões embutidos.

---

## 8. Módulos FARTECH (Gestão Interna)

Registrados com prefixo próprio no `main.py`:

| Prefixo | Router | Domínio |
|---|---|---|
| `/cargos` | `cargo.py` | Cargos profissionais |
| `/filiais` | `filial.py` | Unidades/filiais |
| `/funcionarios` | `funcionario.py` | RH |
| `/chamados` | `chamado.py` | API REST de chamados |
| `/pecas` | `peca.py` | Estoque de peças |
| `/orcamentos` | `orcamento.py` | Orçamentos de reparo |

---

## 9. Integração com Supabase

| Funcionalidade | Mecanismo |
|---|---|
| Auth / Login | Supabase Auth REST API (`/auth/v1/token`) |
| Verificação JWT | JWKS endpoint ES256 (`/auth/v1/.well-known/jwks.json`) |
| Persistência | PostgreSQL direto via SQLAlchemy (connection pooler) |
| Storage | `storage_service.py` (bucket para logos) |

---

## 10. Variáveis de Ambiente (.env)

```env
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
DATABASE_URL=postgresql+psycopg://postgres.<id>:<pass>@aws-0-<region>.pooler.supabase.com:6543/postgres
SUPABASE_JWT_SECRET=...
ANTHROPIC_API_KEY=...
DEBUG=false
```

---

## 11. Dados de Teste (POLSEC)

**Tenant ID:** `dd3ce17e-b506-46cf-9cce-707b20d1e253`

| Usuário | Senha | Perfil |
|---|---|---|
| `admin@polsec.app.br` | `Polsec@2026` | administrador |
| `tecnico@polsec.app.br` | `Tecnico@2026` | operador |
| `viewer@polsec.app.br` | `Viewer@2026` | visualizador |

**Patrimônios de teste:** TI-001 a TI-003 (equipamentos TI), EL-001 … EL-002 (elétrico), MO-001 (mobiliário)

---

## 12. Histórico de Commits Relevantes

| Commit | Descrição |
|---|---|
| `beca4ab` | auth.py persistido + seed de usuários de teste |
| `16f4c4b` | Sistema de SLA por prioridade com badges e config admin |
| `9f262e9` | Fix link Novo Chamado + 6 patrimônios de teste POLSEC |
| `64a6469` | Novo chamado como modal no painel do técnico |
| `b7bc7e1` | Formulário de abertura de chamado |
| `1d21c98` | Login fallback — busca tenant_slug no banco se ausente do JWT |
| `699c955` | Visões completas por hierarquia |
| `64660f0` | Telas superadmin FARTECH separadas da interface POLSEC |
| `9ffc5b9` | Login ES256 JWKS + cookie tenant_slug |

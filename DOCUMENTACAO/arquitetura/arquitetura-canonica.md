# Arquitetura Canônica — Sistema Patrimonial POLSEC/FARTECH

> **Versão:** 4.2  
> **Data:** 09/04/2026  
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
| Criptografia | cryptography (Fernet / AES-128-CBC) | ≥42.0.0 |
| Validação settings | pydantic-settings | — |
| Container | Docker | 24+ |
| Orquestração local | Docker Compose | v2 |
| Automação | Make | — |

---

## 3. Estrutura de Diretórios

```
backend/
├── Dockerfile                    # Multi-stage build (builder + runtime, non-root app:app)
├── docker-compose.yml            # Dev: hot-reload, bind mount app/, env_file .env
├── Makefile                      # Atalhos: install, dev, up, build, migrate, seed, gen-key, audit
├── README.md                     # Documentação pública do projeto
├── run.py                        # Entry point: uvicorn; reload=settings.DEBUG (não fixo)
├── seed_sla.py                   # Migração + seed dos SLAs padrão
├── criar_usuarios_teste.py       # Script de seed de usuários de teste
├── importar_patrimonio.py        # Importação da planilha FOR IE02 para o banco
├── importar_chamados.py          # Importação histórica de chamados (XLSX)
├── importar_faturamento_real.py  # Importação histórica de faturamento (XLSX)
├── importar_diesel.py            # Importação histórica de diesel (XLSX)
├── requirements.txt
├── migrations/
│   ├── 001_sla_configs.sql       # DDL da tabela sla_configs
│   ├── 002_faturamento_historico.sql  # DDL tabela faturamento_historico + índices
│   ├── 003_glosa_chamados.sql    # DDL glosa_faixas + glosa_chamados + colunas SLA em chamados
│   └── 004_diesel.sql            # DDL tabela gastos_diesel + índices
├── app/
│   ├── main.py                   # Criação do app FastAPI, routers, middleware
│   ├── config.py                 # Settings via pydantic-settings (.env)
│   ├── database.py               # Engine SQLAlchemy, SessionLocal, Base
│   ├── middleware/
│   │   ├── tenant.py             # TenantMiddleware — injeta tenant no request
│   │   ├── security.py           # SecurityHeadersMiddleware — CSP, HSTS, X-Frame-Options
│   │   └── rate_limit.py         # LoginRateLimitMiddleware — 5 tentativas/IP/15 min
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
│   │   ├── sla.py                # SLAConfig — prazos por tenant + prioridade
│   │   ├── glosa.py              # GlosaFaixa + GlosaChamado — penalidade contratual
│   │   ├── diesel.py             # GastoDiesel — controle de abastecimento
│   │   └── faturamento.py        # FaturamentoHistorico — fechamentos por unidade/período
│   ├── routers/                  # Handlers HTTP por domínio
│   │   ├── _shared.py            # Helpers compartilhados: exigir_admin(), brl() formatador BRL
│   │   ├── auth.py               # Login/logout (Supabase + cookie httponly)
│   │   ├── dashboard.py          # Redireciona por perfil
│   │   ├── superadmin.py         # Interface FARTECH (gestão de tenants)
│   │   ├── admin.py              # Interface Administrador POLSEC (dashboard, chamados,
│   │   │                         #   funcionários, faturamento, DRE, diesel — via /admin/*)
│   │   ├── tecnico.py            # Interface Técnico (perfil operador)
│   │   ├── patrimonio.py
│   │   ├── movimentacao.py
│   │   ├── chamado.py            # API REST de chamados
│   │   ├── cargo.py
│   │   ├── filial.py
│   │   ├── funcionario.py
│   │   ├── peca.py
│   │   ├── orcamento.py
│   │   ├── glosa.py              # CRUD de glosas + relatórios
│   │   ├── diesel.py             # CRUD de gastos diesel
│   │   ├── assistente.py         # Chat IA (Anthropic Claude)
│   │   ├── da.py                 # Data Analytics
│   │   └── tenant.py             # Auto-registro de empresa
│   ├── security/
│   │   ├── __init__.py
│   │   └── audit.py              # Auditoria automática diária — 5 verificações de segurança
│   ├── services/
│   │   ├── auth_service.py       # Verificação JWT ES256 via JWKS, get_usuario_logado
│   │   ├── chamado_service.py    # Lógica de negócio de chamados
│   │   ├── sla_service.py        # Cálculo de SLA em lote, seed de prazos padrão
│   │   ├── patrimonio_service.py
│   │   ├── tenant_service.py
│   │   ├── da_service.py
│   │   ├── llm_service.py        # Integração Anthropic Claude (aceita api_key por tenant)
│   │   ├── config_service.py     # TenantConfigService — configurações sensíveis com Fernet
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
│   │   │   ├── chamados.html          # Gestão de chamados (atribuir, fechar)
│   │   │   ├── chamados_relatorio.html # Análise SLA (chamados abertos, KPIs, filtros)
│   │   │   ├── funcionarios.html
│   │   │   ├── usuarios.html
│   │   │   ├── sla.html               # Configuração de SLA por prioridade
│   │   │   ├── integracoes.html       # Configuração da chave API Claude por tenant
│   │   │   ├── faturamento.html       # Fechamento de faturamento mensal
│   │   │   ├── faturamento_historico.html
│   │   │   ├── faturamento_relatorio.html # Relatório anual cross-unidade
│   │   │   ├── dre.html               # DRE simplificado
│   │   │   ├── diesel.html            # Lista de abastecimentos
│   │   │   ├── diesel_form.html       # Novo / editar abastecimento
│   │   │   ├── glosa.html             # Lista de glosas
│   │   │   ├── glosa_form.html
│   │   │   ├── glosa_detalhe.html
│   │   │   ├── glosa_faixas.html      # Tabela de percentuais por faixa
│   │   │   └── glosa_relatorio.html
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
| `sla_configs` | Prazos de SLA por tenant e prioridade |
| `glosa_faixas` | Tabela de percentuais de penalidade por faixa de horas (por tenant) |
| `glosa_chamados` | Registros de glosa vinculados opcional a chamados |
| `gastos_diesel` | Controle de abastecimentos de diesel por tenant |
| `faturamento_historico` | Fechamentos de faturamento por unidade/mês/ano (origem: sistema ou importação) |

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
  │  Resolve tenant slug na ordem:
  │    1. Subdomínio (host com ≥3 partes, exceto www/app/api)
  │       ⚠️ IPs (ex: 127.0.0.1) e localhost são ignorados nesta etapa
  │    2. Header X-Tenant-Slug
  │    3. Cookie tenant_slug
  │  Injeta request.state.tenant
  ▼
auth_service.get_usuario_logado()
  │  Lê cookie access_token
  │  Busca JWKS em <SUPABASE_URL>/auth/v1/.well-known/jwks.json (algoritmo ES256)
  │  Verifica assinatura + expiração
  │  Busca Usuario no DB por supabase_uid
  │  Loga resultado: AUTH OK / AUTH FAIL com motivo (logger polsec.auth)
  ▼
Dependência FastAPI injetada nos routers
```

> **Nota de implementação — IPs vs subdomínios:** ao rodar localmente (`127.0.0.1`),
> dividir o host por `.` produziria `["127","0","0","1"]` (4 partes ≥ 3), fazendo o
> middleware interpretar `"127"` como tenant slug, quebrando o login. O middleware
> detecta endereços IPv4 via regex antes de tentar extrair subdomínio, pulando direto
> para o fallback de cookie (`tenant_slug`). Commit `f4537dc`.

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

> **Logo:** ambos `base.html` e `base_tecnico.html` exibem a logo POLSEC via URL pública do Supabase Storage (`POLSEC_MARCA_Artboard 1 copy 16.png`) no topo do sidebar, substituindo o texto anterior.

### Sidebar Admin (`base.html`) — Seções

A sidebar do perfil `administrador` é dividida em quatro seções:

| Seção | Itens | Rota base |
|---|---|---|
| **Operacional** | Análise SLA, Chamados, Funcionários, Diesel | `/admin/chamados/relatorio`, `/admin/chamados`, `/admin/funcionarios`, `/admin/diesel/` |
| **Financeiro** | Faturamento, Hist. Faturamento, Relatório Anual, DRE, Glosa | `/admin/faturamento`, `/admin/faturamento/historico`, `/admin/faturamento/relatorio`, `/admin/dre`, `/admin/glosa` |
| **Sistema** | SLA, Acessos, Integrações IA | `/admin/sla`, `/admin/usuarios`, `/admin/integracoes` |
| **Inteligência** | Assistente IA, Data Analytics | `/assistente`, `/da` |

> **Active state:** o link "Análise SLA" ativa apenas em `/admin/chamados/relatorio` (exact match).  
> O link "Chamados" usa `startswith('/admin/chamados') and path != '/admin/chamados/relatorio'`.

### Fluxo de Redirecionamento por Perfil

```
GET /dashboard
  ├── superadmin    → /superadmin
  ├── administrador → /dashboard (visão KPIs + gráficos)
  ├── operador      → /tecnico (painel de chamados)
  └── visualizador  → /dashboard (somente leitura)
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
ANTHROPIC_API_KEY=...   # fallback global; cada tenant pode sobrescrever via /admin/integracoes
SECRET_KEY=...          # chave Fernet para cifrar dados sensíveis (gere com Fernet.generate_key())
DEBUG=false
SEC_AUDIT_DIR=/tmp      # diretório de relatórios de auditoria de segurança (opcional)
```

> **Gerar SECRET_KEY:**
> ```bash
> python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
> ```

---

## 11. Dados de Teste (POLSEC)

**Tenant ID:** `dd3ce17e-b506-46cf-9cce-707b20d1e253`

| Usuário | Senha | Perfil |
|---|---|---|
| `admin@polsec.app.br` | `Polsec@2026` | administrador |
| `tecnico@polsec.app.br` | `Tecnico@2026` | operador |
| `viewer@polsec.app.br` | `Viewer@2026` | visualizador |

**Patrimônios de teste:** TI-001 a TI-003 (equipamentos TI), EL-001 … EL-002 (elétrico), MO-001 (mobiliário)

**Patrimônios importados (planilha FOR IE02):** 8.002 registros com código PAT-00001 a PAT-08004 e série SPAT-XXXXX.

**Total no banco:** 8.008 registros (8.002 importados + 6 de teste).

---

## 12. Script de Importação — `importar_patrimonio.py`

### O que faz

Lê a planilha `FOR IE02 - CONTROLE PATRIMONIAL - V1.numbers` e insere os registros na
tabela `patrimonios` do banco. É **idempotente**: execuções repetidas ignoram registros
cujo código já exista no tenant, sem sobrescrever dados.

Campos não preenchidos na planilha são gravados como `None` (numérico `0` para valor); os
usuários completam o cadastro pela interface web nas próximas atualizações.

### Mapeamento de colunas

| Coluna na planilha | Campo no banco | Observação |
|---|---|---|
| PAT. (0) | `codigo` | Numérico → `PAT-00001`; texto → `SPAT-00001`; vazio → `IMP-00001` |
| EQUIPAMENTO (1) | `descricao` | Máx. 255 caracteres |
| UNIDADE (3) | `setor` | Máx. 100 caracteres |
| LOCAL (4) | `localizacao` | Máx. 150 caracteres |
| VALOR (8) | `valor` | Se zero, tenta VALOR UNITÁRIO (col 6) |
| VALOR UNITÁRIO (6) | `valor` (fallback) | Usado quando col 8 está vazia |
| OBSERVAÇÕES (7) + N° SÉRIE (2) + NF (5) | `observacoes` | Concatenados com ` \| ` |
| — | `categoria` | Auto-detectada por palavras-chave na descrição |
| — | `data_aquisicao` | `None` — usuário preenche depois |
| — | `status` | Sempre `ativo` na importação |

### Categorização automática

O script detecta a categoria pelo nome do equipamento:

| Palavras-chave | Categoria atribuída |
|---|---|
| notebook, switch, servidor, rack, onu, olt, sfp, wifi… | TI / Telecomunicações |
| celular, smartphone, tablet, rádio… | Telecom / Mobile |
| antena, torre, fibra, cabo, conector… | Infraestrutura de Rede |
| câmera, dvr, nvr, cftv… | Segurança / CFTV |
| ar condicionado, climatizador… | Climatização |
| gerador, bateria… | Energia |
| mesa, cadeira, armário… | Mobiliário |
| (nenhuma) | Não categorizado |

### Pré-requisitos

```bash
# 1. Ativar ambiente virtual
source .venv/bin/activate

# 2. Instalar dependência extra (só na primeira vez)
pip install numbers-parser
```

### Como usar

**1. Simulação (dry-run) — NÃO grava nada no banco:**

```bash
python importar_patrimonio.py --dry-run
```

Exibe o relatório completo (quantos seriam inseridos, ignorados, erros) sem tocar no banco.
Sempre execute este passo antes de importar de verdade.

---

**2. Importação real com valores padrão** (tenant POLSEC + caminho padrão do arquivo):

```bash
python importar_patrimonio.py
```

---

**3. Importação especificando tenant e/ou arquivo:**

```bash
python importar_patrimonio.py \
  --tenant-id dd3ce17e-b506-46cf-9cce-707b20d1e253 \
  --arquivo "/Volumes/FDIAS 320 GB/FOR IE02 - CONTROLE PATRIMONIAL - V1.numbers"
```

---

**4. Importação para outro tenant** (ex.: novo cliente):

```bash
python importar_patrimonio.py \
  --tenant-id <UUID-DO-NOVO-TENANT> \
  --arquivo "/caminho/para/planilha-do-cliente.numbers"
```

---

**5. Salvar log em arquivo** (útil para importações grandes):

```bash
python -u importar_patrimonio.py > /tmp/import_log.txt 2>&1
cat /tmp/import_log.txt
```

### Saída esperada

```
Importando: FOR IE02 - CONTROLE PATRIMONIAL - V1.numbers
Tenant ID : dd3ce17e-b506-46cf-9cce-707b20d1e253
------------------------------------------------------------
  → 500 registros inseridos até agora...
  → 1000 registros inseridos até agora...
  ...
============================================================
Linhas na planilha  : 8296
Inseridos           : 8002
Ignorados (vazios)  : 292
Ignorados (duplic.) : 2
Erros               : 0
============================================================
Importação concluída.
```

> **Nota:** Commits em lotes de 500 registros evitam transações excessivamente longas.

### Comportamento em re-execuções

| Situação | Comportamento |
|---|---|
| Registro com código já existente no tenant | Ignorado (`Ignorados (duplic.)` +1) |
| Linha completamente vazia | Ignorado (`Ignorados (vazios)` +1) |
| Erro em um registro específico | Registrado no terminal; os demais continuam |
| Execução repetida após importação completa | `Inseridos: 0` — sem duplicatas |

### Campos que o usuário deve completar pelo sistema

Após a importação os campos abaixo ficam em branco e devem ser preenchidos pela equipe:

- **Data de aquisição** — `data_aquisicao` (None)
- **Responsável** — `responsavel_id` (None)
- **Valor**, quando não constava na planilha — `valor` (None)
- **Categoria** — pode ser corrigida manualmente se a auto-detecção errou
- **Status** — ajuste para `manutencao`, `baixado` ou `extraviado` conforme necessário

Acesse: **Sistema → Patrimônios → [Bem] → Editar**

---

## 13. Lista de Patrimônios — Paginação e Filtros

Com 8.008 registros no banco, a lista de patrimônios usa paginação server-side para evitar carregar todos os registros de uma vez (commit `57d7b08`).

### Comportamento

| Parâmetro de query | Descrição | Padrão |
|---|---|---|
| `page` | Número da página atual | `1` |
| `busca` | Busca em `codigo`, `descricao` e `localizacao` | — |
| `categoria` | Filtro por categoria auto-detectada | — |
| `setor` | Filtro por setor | — |
| `status_filtro` | Filtro por status (`ativo`, `manutencao`, etc.) | — |

- **50 registros por página** (configurável via `PatrimonioService.PER_PAGE`)
- `PatrimonioService.listar()` retorna `(itens, total, total_pages)` usando `LIMIT/OFFSET`
- `listar_categorias()` — retorna categorias distintas para o select de filtro
- `contar_por_status()` — agrega contagem por status para os KPI cards

### KPI cards na listagem

| Card | Consulta |
|---|---|
| Total (filtrado) | `total` retornado pelo `listar()` com filtros aplicados |
| Ativos | `contar_por_status()['ativo']` (sempre do tenant completo) |
| Manutenção | `contar_por_status()['manutencao']` |
| Baixados + Extraviados | soma de `baixado` + `extraviado` |

---

## 15. Suporte Offline — PWA + Service Worker + IndexedDB

Os técnicos operam em presídios sem sinal de internet. O sistema funciona offline e sincroniza automaticamente ao reconectar.

### Arquitetura de Camadas

```
[Técnico offline]
       │
       ▼ submit de form
[offline.js — intercepta form submit]
       │ navigator.onLine === false
       ▼
[IndexedDB: polsec-offline-v1]
  store: sync_queue
  {id, url, method, body, label, timestamp, status}
       │
       ▼ window.online event
[syncQueue() — replay POST requests]
       │
       ▼
[FastAPI — endpoints existentes]
```

### Service Worker (`/sw.js` → `app/static/js/sw.js`)

| Tipo de request | Estratégia |
|---|---|
| `/static/**`, CDN jsdelivr.net | **Cache-first** — serve do cache, atualiza em background |
| HTML pages (same-origin GET) | **Network-first** — tenta rede, fallback ao cache |
| POST requests | **Ignorado** — tratado pelo `offline.js` via JS |

**Pré-cache no install:** `style.css`, `main.js`, `offline.js`, Bootstrap CSS/JS/Icons (CDN)

### offline.js (`/static/js/offline.js`)

| Função | Responsabilidade |
|---|---|
| `openDB()` | Abre `polsec-offline-v1` v1, cria store `sync_queue` |
| `enqueue(op)` | Salva operação pendente no IndexedDB |
| `getPendingOps()` | Retorna operações com `status:'pending'` ordenadas por timestamp |
| `updateOpStatus(id, s)` | Marca `synced` ou `failed` |
| `interceptForms()` | Captura `submit` quando offline → IndexedDB (ignora `[data-no-offline]`) |
| `syncQueue()` | Itera pendentes, replays via `fetch()`, reload em 2s se tudo OK |
| `showBanner(state, n)` | Banner fixo: offline (vermelho) / syncing (laranja) / synced (verde) |
| `showToast(msg, type)` | Notificação bottom-right |
| `registerSW()` | Registra `/sw.js` com scope `/` |

### PWA Manifest (`/manifest.json` → `app/static/manifest.json`)

```json
{
  "name": "POLSEC — Gestão Patrimonial",
  "short_name": "POLSEC",
  "start_url": "/dashboard",
  "display": "standalone",
  "theme_color": "#ff4e17"
}
```

### Rotas adicionadas no `main.py`

```
GET /sw.js           → FileResponse(app/static/js/sw.js) + Service-Worker-Allowed: /
GET /manifest.json   → FileResponse(app/static/manifest.json)
```

### Templates atualizados

Todos os base templates (`base.html`, `base_tecnico.html`, `base_superadmin.html`) receberam:
```html
<link rel="manifest" href="/manifest.json"/>
<meta name="theme-color" content="#ff4e17"/>
<!-- ... -->
<script src="/static/js/offline.js" defer></script>
```

O form de login (`login.html`) recebeu `data-no-offline` — nunca é enfileirado.

### Cenário de operação offline

1. Técnico visita o sistema **online** → Service Worker cacheia páginas e assets
2. Técnico entra no presídio (**sem sinal**) → banner vermelho aparece
3. Técnico atualiza status de chamado → form interceptado → salvo no IndexedDB
4. Ao sair do presídio (**sinal volta**) → `syncQueue()` dispara automaticamente
5. Operações são reenviadas para os endpoints originais por ordem de timestamp
6. Página recarrega após 2s → dados atualizados exibidos

### Edge cases documentados

- **Cookie expirado após ausência longa (>7d):** sync redireciona para login (aceitável)
- **Conflito de edição:** last-write-wins por ordem de timestamp
- **Páginas não cacheadas offline:** SW silenciosamente não serve (usuário vê erro de rede normal)

---

## 20. Análise SLA (`/admin/chamados/relatorio`)

Página exclusiva para o perfil `administrador`. Exibe apenas chamados com status **aberto**.

### Comportamento dos filtros

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `mes` | `0` (Todos) | Mês de abertura (0 = sem filtro) |
| `ano` | `0` (Todos) | Ano de abertura (0 = sem filtro) |
| `tipo` | `""` (Todos) | `preventiva` ou `corretiva` |
| `filial_id` | `""` (Todas) | Filtra por filial do patrimônio |

Quando `mes=0` e `ano=0` (padrão), nenhum filtro de data é aplicado — **todos os chamados abertos** do tenant são exibidos (limite 500).

### KPIs exibidos

- Total de chamados abertos
- Preventivas / Corretivas
- Tempo médio de chegada do técnico (min)
- Tempo médio de resolução (h)
- Quantidade com glosa

### Fix de timezone

Chamados importados de planilhas têm `data_abertura` com timezone UTC, enquanto chamados criados pelo sistema são naive. A função auxiliar `_naive(dt)` normaliza todos os datetimes antes de calcular deltas:

```python
def _naive(dt):
    if dt is None: return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt
```

### Performance

Query usa `joinedload` para todos os relacionamentos acessados no template (`patrimonio`, `solicitante`, `tecnico`, `glosas`) — evita N+1 mesmo com 400+ registros.

---

## 21. Módulo Glosa (`/admin/glosa`)

Controle de penalidade contratual por indisponibilidade de serviço.

### Modelos

| Modelo | Tabela | Descrição |
|---|---|---|
| `GlosaFaixa` | `glosa_faixas` | Percentuais por faixa de horas (configurável por tenant) |
| `GlosaChamado` | `glosa_chamados` | Registro individual de penalidade |

### Faixas padrão POLSEC

| Faixa (h) | Penalidade |
|---|---|
| 1 – 24 h | 2% |
| 24 – 60 h | 4% |
| 60 – 168 h | 8% |
| 168 – 240 h | 16% |
| > 240 h | 32% |

### StatusGlosa

`ativa` → `encerrada` | `contestada` | `cancelada`

### Rotas

| Rota | Descrição |
|---|---|
| `GET /admin/glosa` | Lista de glosas com filtros mes/ano/status |
| `GET /admin/glosa/novo` | Formulário de registro de nova glosa |
| `POST /admin/glosa` | Salvar nova glosa |
| `GET /admin/glosa/{id}` | Detalhe da glosa |
| `POST /admin/glosa/{id}/encerrar` | Encerrar + calcular valor |
| `GET /admin/glosa/faixas` | Configurar tabela de percentuais |
| `GET /admin/glosa/relatorio` | Relatório consolidado por período |

### Relacionamento com Chamado

`Chamado.glosas` → `GlosaChamado` (back_populates em ambos os modelos). Um chamado pode ter N glosas. Glosa pode existir sem chamado (lançamento manual retroativo — `chamado_id` nullable).

---

## 22. Módulo Diesel (`/admin/diesel/`)

Controle de abastecimentos de óleo diesel por tenant.

### Modelo

`GastoDiesel` → tabela `gastos_diesel`

| Campo | Tipo | Descrição |
|---|---|---|
| `data` | DateTime | Data do abastecimento |
| `numero_nota` | Integer, nullable | Número do registro na planilha |
| `descricao` | String(300) | Ex: "Abastecimento Óleo Diesel - Limeira" |
| `local` | String(150) | Unidade/local extraído |
| `tecnico` | String(150) | Motorista / responsável |
| `litros` | Numeric(10,3) | Quantidade |
| `valor_litro` | Numeric(8,3) | Preço por litro |
| `valor_total` | Numeric(12,2) | Valor total pago |

### Formulário inteligente

No form de novo/editar abastecimento (`diesel_form.html`):
- Campo `local` é um `<select>` populado com as filiais ativas do tenant
- Opção "Outro…" revela um campo de texto livre
- Ao selecionar uma filial, a `descricao` é auto-preenchida como `"Abastecimento Óleo Diesel - [Nome da Filial]"` (editável)
- O valor do select é carregado via campo hidden `localHidden` no POST

### Rotas

| Rota | Descrição |
|---|---|
| `GET /admin/diesel/` | Lista com filtros mes/ano |
| `GET /admin/diesel/novo` | Formulário novo |
| `POST /admin/diesel/novo` | Salvar |
| `GET /admin/diesel/{id}/editar` | Formulário edição |
| `POST /admin/diesel/{id}/editar` | Atualizar |
| `POST /admin/diesel/{id}/excluir` | Excluir |

### Script de importação

```bash
PYTHONPATH=. .venv/bin/python3 importar_diesel.py "<arquivo.xlsx>" --tenant polsec
```

---

## 23. Módulo Faturamento (`/admin/faturamento`)

Fechamento mensal de faturamento por unidade/filial.

### Modelo

`FaturamentoHistorico` → tabela `faturamento_historico`

Restrição de unicidade: `(tenant_id, filial_nome, mes, ano, origem)` — impede duplicatas por período.

| Campo | Descrição |
|---|---|
| `filial_nome` | Snapshot do nome (preservado mesmo que a filial seja renomeada) |
| `chamados_count` | Quantidade de chamados no período |
| `valor_mao_obra` | Valor de mão de obra |
| `valor_pecas` | Valor de peças |
| `valor_total` | Total cobrado |
| `origem` | `"sistema"` (fechamento manual) ou `"importacao"` (xlsx legado) |

### Rotas

| Rota | Descrição |
|---|---|
| `GET /admin/faturamento` | Fechamento mensal atual — lista unidades com valores |
| `GET /admin/faturamento/historico` | Histórico de todos os fechamentos |
| `GET /admin/faturamento/relatorio` | Relatório anual cross-unidade (tabela pivô) |
| `GET /admin/dre` | DRE simplificado (receitas vs despesas) |

### Script de importação

```bash
PYTHONPATH=. .venv/bin/python3 importar_faturamento_real.py "<FATURAMENTO.xlsx>" --tenant polsec
```

**Saída:** relatório com `[INS]` / `[UPD]` / `[IGN]` por ABA da planilha.

---

## 24. Scripts de Importação de Dados Históricos

| Script | Fonte | O que importa |
|---|---|---|
| `importar_patrimonio.py` | `.numbers` (FOR IE02) | Patrimônios — idempotente por código |
| `importar_chamados.py` | `.xlsx` (Controle SP) | Chamados históricos — idempotente por número |
| `importar_faturamento_real.py` | `.xlsx` (FATURAMENTO) | Faturamento histórico por unidade/mês |
| `importar_diesel.py` | `.xlsx` (Diesel) | Abastecimentos históricos |

Todos os scripts são **idempotentes** — re-execuções ignoram registros já existentes sem sobrescrever.

---

## 25. Dashboard (`/dashboard`)

Acessado por `administrador` e `visualizador`. Superadmin redireciona para `/superadmin`, operador para `/tecnico`.

### Variáveis injetadas pelo `dashboard.py`

| Variável | Tipo | Descrição |
|---|---|---|
| `total` | int | Total de patrimônios do tenant |
| `status_map` | dict | Contagens por status: `ativo`, `manutencao`, `baixado`, `extraviado` |
| `por_setor` | list[tuple] | Top 10 setores por quantidade (nome, qty) |
| `fat_total_hist` | float | Soma histórica de faturamento (todas as origens) |
| `ultimo_fat` | Row\|None | Último mês fechado: `.mes`, `.ano`, `.total`, `.unidades` |
| `chamados_abertos` | int | Chamados com status `aberto` |
| `chamados_em_atendimento` | int | Chamados com status `em_atendimento` |
| `total_filiais` | int | Filiais ativas do tenant |
| `glosa_ativas` | int | Glosas com status `ativa` |
| `glosa_valor_mes` | float | Valor de glosas encerradas no mês corrente |
| `preventivas_abertas` | int | Chamados preventivos em aberto ou em atendimento |
| `diesel_valor_mes` | float | Soma de `GastoDiesel.valor_total` no mês corrente |
| `can_edit` | bool | `False` para perfil `visualizador` |

### Layout atual — `dashboard.html`

| Bloco | Conteúdo |
|---|---|
| KPI cards (linha 1) | Total de bens · Ativos · Em Manutenção · Extraviados |
| Bens por Setor | Gráfico de barras horizontais — top 10 setores |
| Distribuição por Status | Lista com badges coloridos por status |

> **Pendente de implementação (design aprovado 09/04/2026):**  
> Reorganizar `dashboard.html` em três seções com separadores visuais:
> - **Financeiro** — Faturamento histórico, último fechamento, Diesel/mês, Glosa ativas
> - **Operacional** — Chamados em aberto, concluídos no mês, preventivas, unidades
> - **SLA** — Violados, em risco (80–99%), no prazo, % conformidade, tempo médio de resolução
>
> O `dashboard.py` já injeta todas as variáveis necessárias para esse layout.  
> Blocos "Bens por Setor" e "Status do Acervo" serão removidos do template.

---

## 14. Histórico de Commits Relevantes

| Commit | Descrição |
|---|---|
| *(v4.1)* | docs: arquitetura canônica v4.1 — seção Dashboard (variáveis, layout atual, redesign pendente) |
| `32e6c57` | docs: arquitetura canônica v3.7 → v4.0 |
| *(v4.0)* | Análise SLA: filtro todos os períodos por padrão, apenas chamados abertos, joinedload glosas, fix timezone naive/aware |
| *(v4.0)* | Sidebar admin reorganizada: Operacional / Financeiro / Sistema / Inteligência |
| *(v4.0)* | Módulo Diesel: form inteligente com select filial + auto-descrição |
| *(v4.0)* | Módulo Glosa: GlosaFaixa + GlosaChamado, faixas padrão POLSEC |
| *(v4.0)* | Módulo Faturamento + DRE: fechamento mensal, histórico, relatório anual |
| *(v4.0)* | Scripts de importação histórica: chamados, faturamento, diesel |
| `0f81b05` | feat: indicador visual de status da IA (dot verde/vermelho na sidebar + ícone no chat) |
| `bd29b9e` | feat: admin configura chave Claude via interface web — TenantConfigService + Fernet |
| `9fb140e` | security: hardening nível bancário — SecurityHeaders, RateLimit, auditoria diária, OWASP fixes |
| `478675b` | docs: arquitetura canônica v3.5 — TenantMiddleware IP fix |
| `f4537dc` | Fix TenantMiddleware: ignora IPs/localhost ao extrair subdomínio (bug 127→slug) |
| `8beb067` | Onboarding por nível de usuário (modal multi-step, localStorage) |
| `f9ee2e2` | Arquitetura canônica v3.3 — seção PWA offline |
| `4308709` | PWA offline — Service Worker + IndexedDB sync queue |
| `b646f34` | Arquitetura canônica v3.2 — paginação, logo POLSEC, histórico |
| `4e8173f` | Logo POLSEC no sidebar (base.html e base_tecnico.html) |
| `57d7b08` | Paginação + filtro categoria + KPIs na lista de patrimônios (8k+ registros) |
| `9c57c2d` | Arquitetura canônica v3.1 — documentação da importação FOR IE02 |
| `4f03a7e` | Script importar_patrimonio.py — 8.002 patrimônios POLSEC importados |
| `beca4ab` | auth.py persistido + seed de usuários de teste |
| `16f4c4b` | Sistema de SLA por prioridade com badges e config admin |
| `9f262e9` | Fix link Novo Chamado + 6 patrimônios de teste POLSEC |
| `64a6469` | Novo chamado como modal no painel do técnico |
| `b7bc7e1` | Formulário de abertura de chamado |
| `1d21c98` | Login fallback — busca tenant_slug no banco se ausente do JWT |
| `699c955` | Visões completas por hierarquia |
| `64660f0` | Telas superadmin FARTECH separadas da interface POLSEC |
| `9ffc5b9` | Login ES256 JWKS + cookie tenant_slug |

---

## 16. Segurança (Nível Bancário)

Implementado no commit `9fb140e`. Os três mecanismos atuam em camadas no pipeline de middlewares.

### Ordem dos Middlewares

```
Request
  │
  ▼
LoginRateLimitMiddleware  (outermost — protege antes de qualquer processamento)
  │
  ▼
SecurityHeadersMiddleware
  │
  ▼
TenantMiddleware          (innermost — resolve tenant antes dos handlers)
  │
  ▼
FastAPI handlers
```

### SecurityHeadersMiddleware (`app/middleware/security.py`)

| Header | Valor | Proteção |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' cdn.jsdelivr.net ...` | XSS injection |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | Browser XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Leak de URL |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Feature abuse |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS only (HTTPS apenas) |
| `Cache-Control` | `no-store, no-cache` | Páginas autenticadas não cacheadas |

### LoginRateLimitMiddleware (`app/middleware/rate_limit.py`)

- **Janela:** 15 minutos por IP
- **Limite:** 5 tentativas de login falhadas
- **Resposta:** HTTP 429 com header `Retry-After`
- **API pública:** `registrar_falha_login(ip)`, `registrar_sucesso_login(ip)`, `ip_bloqueado(ip)`
- Sucesso no login limpa o contador do IP

### Auditoria Automática Diária (`app/security/audit.py`)

Roda às **02:00** via `asyncio` loop registrado no lifespan do FastAPI.

| Verificação | Critério de alerta |
|---|---|
| Contas estagnadas | Usuários sem login há > 90 dias |
| Excesso de privilégio | Mais de 3 superadmins cadastrados |
| Volume anômalo de auditoria | z-score > 3σ em qualquer tenant |
| UIDs órfãos | Usuários inativos com `supabase_uid` preenchido |
| IPs sob força-bruta | IPs com ≥ 5 falhas na janela de rate limit |

Saída: `/tmp/security_audit_YYYY-MM-DD.json` (configurável via `SEC_AUDIT_DIR`).

Execução manual: `python -m app.security.audit`

### Fixes OWASP (commit `9fb140e`)

- **OWASP A01 (Broken Access Control):** `POST /{patrimonio_id}/editar` usava `Depends(get_usuario_logado)` em vez de `Depends(_exigir_escrita)` — visualizadores podiam editar patrimônios. Corrigido.
- **N+1 no LLM service:** `selectinload` adicionado para `Patrimonio.responsavel`, `Movimentacao.patrimonio` e `Movimentacao.usuario`.
- **Docs/OpenAPI** ocultos em produção (`DEBUG=False`).

---

## 17. Integração IA — Chave Claude por Tenant

Implementado no commit `bd29b9e`.

### Problema

Antes, a chave `ANTHROPIC_API_KEY` era única e global (`.env`). Em um ambiente SaaS multi-tenant, cada cliente deve usar sua própria chave — isolamento de cobrança e de acesso.

### Solução

```
admin acessa /admin/integracoes
  │ cola sk-ant-api03-...
  ▼
TenantConfigService.set_llm_api_key(db, key)
  │ Fernet.encrypt(key) → token cifrado
  ▼
tenant.configuracoes = JSON { "llm_api_key": "<fernet_token>" }
  │ persiste no banco (plaintext NUNCA salvo)
  ▼
request /assistente/chat
  │
TenantConfigService.get_llm_api_key() → decrypt → str
  │ passado como api_key para chat_stream()
  ▼
anthropic.Anthropic(api_key=tenant_key or settings.ANTHROPIC_API_KEY)
```

### TenantConfigService (`app/services/config_service.py`)

| Método | Descrição |
|---|---|
| `set_llm_api_key(db, key)` | Valida prefixo `sk-ant-`, cifra com Fernet, persiste no JSON `configuracoes` |
| `get_llm_api_key()` | Decifra e retorna plaintext — **nunca exposto ao frontend** |
| `get_llm_api_key_masked()` | Retorna `sk-ant-api03-••••••••••••••••XXXX` — seguro para exibição |
| `has_llm_api_key()` | `bool` — indica se o tenant tem chave configurada |
| `remove_llm_api_key(db)` | Remove do JSON e persiste |

### Armazenamento

A chave é armazenada no campo `configuracoes` (Text/JSON) já existente no modelo `Tenant`, sem necessidade de nova coluna:

```json
{ "llm_api_key": "gAAAAAB..." }
```

### Criptografia

- **Algoritmo:** Fernet = AES-128-CBC + HMAC-SHA256
- **Chave mestra:** `SECRET_KEY` no `.env` (gerada com `Fernet.generate_key()`)
- **Biblioteca:** `cryptography>=42.0.0`

### Fallback

Se o tenant não tiver chave configurada, `chat_stream()` usa `settings.ANTHROPIC_API_KEY` do `.env` — compatibilidade retroativa garantida.

### Interface Admin

`GET /admin/integracoes` — exibe estado atual (chave mascarada ou aviso de ausência)  
`POST /admin/integracoes` — salvar nova chave ou remover existente  
Link na sidebar: **Sistema → Integrações IA** (visível para `administrador` e `superadmin`)

### Indicador Visual de Status (`0f81b05`)

`GET /assistente/status` — endpoint JSON protegido por auth, retorna `{"conectado": bool}`.  
Usado por dois mecanismos:

1. **Sidebar** (`base.html`, `base_tecnico.html`): dot circular `8×8 px` ao lado de "Assistente IA"  
   - Cinza enquanto carrega → **verde** `#198754` se `conectado: true` → **vermelho** `#dc3545` se `false`  
   - Preenchido via `fetch('/assistente/status')` no load de qualquer página

2. **Página do chat** (`chat.html`): renderizado server-side via Jinja (`ia_conectada`)  
   - Ícone `bi-robot` → `text-success` (verde) ou `text-danger` (vermelho)  
   - Badge: `● Conectado · Claude` (verde) ou `● Sem chave configurada` (vermelho)

---

## 18. Onboarding por Nível de Usuário

Modal de boas-vindas exibido na **primeira visita** de cada perfil, controlado via `localStorage`.

### Implementação

| Arquivo | Função |
|---|---|
| `app/static/js/onboarding.js` | Modal JS puro (sem dependência extra), lê `data-perfil` do `<body>` |
| `base.html`, `base_tecnico.html`, `base_superadmin.html` | Inject `data-perfil="{{ usuario.perfil.value }}"` no `<body>` + `<script onboarding.js defer>` |

### Controle de exibição

```js
localStorage.getItem('polsec_onboarding_v1_<perfil>') === '1'  // já viu
localStorage.setItem('polsec_onboarding_v1_<perfil>', '1')      // marcar visto
```

Para forçar re-exibição do onboarding (debug / reset):
```js
// Console do browser
localStorage.removeItem('polsec_onboarding_v1_administrador')
```

---

## 19. Comandos de Operação

```bash
# ── Setup inicial ────────────────────────────────────────────────────────────
cd SISTEMA-PATRIMONIAL/backend
cp .env.example .env            # copiar e preencher variáveis
make install                    # cria .venv + pip install -r requirements.txt

# ── Desenvolvimento local ─────────────────────────────────────────────────────
make dev                        # uvicorn com hot-reload (DEBUG=true no .env)
# equivalente manual:
source .venv/bin/activate && python run.py

# ── Docker ───────────────────────────────────────────────────────────────────
make up                         # docker compose up --build (dev com bind mount)
make build                      # docker build imagem de produção polsec-api:latest
make down                       # para containers
make logs                       # docker compose logs -f api
make shell                      # bash dentro do container

# ── Banco de dados ────────────────────────────────────────────────────────────
make migrate                    # aplica todos os migrations/0*.sql
make seed                       # popula SLAs padrão (seed_sla.py)
make seed-users                 # cria usuários de teste (criar_usuarios_teste.py)

# ── Segurança ─────────────────────────────────────────────────────────────────
make gen-key                    # gera nova SECRET_KEY Fernet
make audit                      # auditoria de segurança manual
python -m app.security.audit    # alternativa direta

# ── Importação de dados históricos ───────────────────────────────────────────
PYTHONPATH=. .venv/bin/python3 importar_patrimonio.py --dry-run
PYTHONPATH=. .venv/bin/python3 importar_patrimonio.py
PYTHONPATH=. .venv/bin/python3 importar_chamados.py "arquivo.xlsx" --tenant polsec
PYTHONPATH=. .venv/bin/python3 importar_faturamento_real.py "FATURAMENTO.xlsx" --tenant polsec
PYTHONPATH=. .venv/bin/python3 importar_diesel.py "diesel.xlsx" --tenant polsec
```

### Conteúdo por Perfil

| Perfil | Steps | Destaque |
|---|---|---|
| `superadmin` | 3 | Plataforma FARTECH, gestão de tenants, acesso privilegiado |
| `administrador` | 4 | Dashboard KPIs, patrimônios, chamados+SLA, usuários |
| `operador` | 3 | Painel chamados, atualizar status, modo offline offline |
| `visualizador` | 2 | Acesso somente leitura, o que pode visualizar |

### Design do Modal

- Progress bar colorida por perfil (laranja POLSEC ou azul técnico)
- Botões: **Próximo / Anterior / Entendido! / Pular**
- Fecha ao clicar no backdrop
- Sem dependência de Bootstrap Modal (DOM próprio, z-index 1055)
- Compatível com PWA (funciona offline, assets já cacheados pelo SW)

---

## 26. Infraestrutura e Deploy (Docker)

### Dockerfile (multi-stage)

| Stage | Base | Responsabilidade |
|---|---|---|
| `builder` | `python:3.12-slim` | Instala dependências de compilação + gera wheels |
| `runtime` | `python:3.12-slim` | Copia apenas as wheels, sem ferramentas de build |

Características adicionais:
- Usuário não-root `app:app` (UID 1001) — nunca roda como root
- `WORKDIR /app`
- Healthcheck: `curl http://localhost:8000/health` a cada 30s
- CMD de produção: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`
- Arquivos desnecessários em produção são removidos do stage final (scripts de importação, *.md, tests/)

### docker-compose.yml (desenvolvimento)

```yaml
# executar com: docker compose up --build
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./app:/app/app   # hot-reload: qualquer mudança em app/ recarrega
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3
```

> O `docker-compose.yml` é **somente para desenvolvimento local**. Em produção, use a imagem built com `make build`.

### Makefile — Referência de Comandos

| Comando | Ação |
|---|---|
| `make install` | `python3 -m venv .venv && pip install -r requirements.txt` |
| `make dev` | `python run.py` (hot-reload quando `DEBUG=true`) |
| `make up` | `docker compose up --build` |
| `make down` | `docker compose down` |
| `make build` | `docker build --target runtime -t polsec-api:latest .` |
| `make logs` | `docker compose logs -f api` |
| `make shell` | `docker compose exec api /bin/bash` |
| `make migrate` | Aplica todos os SQLs em `migrations/0*.sql` via SQLAlchemy AUTOCOMMIT |
| `make seed` | `python seed_sla.py` |
| `make seed-users` | `python criar_usuarios_teste.py` |
| `make gen-key` | Gera nova `SECRET_KEY` Fernet |
| `make audit` | Auditoria de segurança manual |

### Endpoint de Health Check

```
GET /health
Response: {"status": "ok", "version": "2.0.0"}
HTTP 200
```

Implementado em `app/main.py` com `include_in_schema=False` (não aparece no OpenAPI).  
Usado pelo Dockerfile healthcheck e por load balancers externos.

### Pré-requisitos de Produção

1. Banco Supabase criado e schema aplicado (`supabase_schema.sql`)
2. Migrations aplicadas (`make migrate`)
3. `.env` preenchido com todas as variáveis (ver seção 10)
4. `SECRET_KEY` gerada com Fernet (`make gen-key`)
5. Docker 24+ instalado

### Guia de Deploy Rápido

```bash
# 1. Clonar e entrar na pasta
git clone https://github.com/fartech2025/POLSEC.git
cd POLSEC/SISTEMA-PATRIMONIAL/backend

# 2. Configurar ambiente
cp .env.example .env
# → editar .env com credenciais Supabase, ANTHROPIC_API_KEY, SECRET_KEY

# 3. Build e iniciar
make build
docker run --env-file .env -p 8000:8000 polsec-api:latest
# → acesse http://localhost:8000
```

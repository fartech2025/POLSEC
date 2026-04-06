# Arquitetura Canônica — Sistema Patrimonial POLSEC/FARTECH

> **Versão:** 3.3  
> **Data:** 03/04/2026  
> **Commit HEAD:** `4308709`  
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
├── importar_patrimonio.py        # Importação da planilha FOR IE02 para o banco
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

> **Logo:** ambos `base.html` e `base_tecnico.html` exibem a logo POLSEC via URL pública do Supabase Storage (`POLSEC_MARCA_Artboard 1 copy 16.png`) no topo do sidebar, substituindo o texto anterior.

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

## 14. Histórico de Commits Relevantes

| Commit | Descrição |
|---|---|
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

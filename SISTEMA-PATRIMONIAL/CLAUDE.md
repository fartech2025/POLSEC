# POLSEC — Sistema de Gestão Patrimonial SaaS
## Arquitetura Canônica (atualizado 2026-04-09 — rev 3)

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.111 + Python 3.12 |
| Templates | Jinja2 + Bootstrap 5.3 (SSR, sem SPA) |
| ORM | SQLAlchemy 2.0 (psycopg3) |
| Banco | Supabase PostgreSQL 17.6 — porta 5432 direto |
| Auth | Supabase Auth — JWT **ES256** via cookie `access_token` |
| IA | Claude claude-opus-4-6 — tool_use agêntico + SSE streaming |
| Análise | Claude claude-opus-4-6 — Data Analytics com adaptive thinking |
| MCP | FastMCP — servidor standalone para Claude Desktop |
| Storage | Supabase Storage — bucket `polsec-anexos` + Pillow (WebP Q75) |

---

## Estrutura do projeto

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + middleware + routers
│   ├── config.py                # Pydantic Settings — lê .env
│   ├── database.py              # Engine SQLAlchemy + get_db()
│   ├── middleware/
│   │   ├── tenant.py            # TenantMiddleware — resolve slug: subdomínio > header > cookie
│   │   ├── rate_limit.py
│   │   └── security.py
│   ├── models/
│   │   ├── tenant.py            # Tenant (id UUID, slug, nome, plano, ativo)
│   │   ├── usuario.py           # Usuario (supabase_uid, tenant_id, perfil)
│   │   ├── patrimonio.py        # Patrimonio (tenant_id, codigo, status, responsavel_id)
│   │   ├── movimentacao.py      # Movimentacao (tenant_id, tipo)
│   │   ├── audit_log.py         # AuditLog (tenant_id, acao, tabela)
│   │   ├── cargo.py             # Cargo (nivel_hierarquico 1-7, permissoes JSON)
│   │   ├── filial.py            # Filial (tenant_id, responsavel_id)
│   │   ├── funcionario.py       # Funcionario (gestor_id auto-ref, cargo_id, filial_id, usuario_id nullable)
│   │   ├── chamado.py           # Chamado (status machine 7 estados) + AnexoChamado
│   │   ├── peca.py              # Peca + EstoqueGeral + EstoqueFilial + PecaChamado
│   │   ├── orcamento.py         # Orcamento + AprovacaoOrcamento (audit) + NotaFiscal
│   │   ├── sla.py               # SLAConfig (prioridade, tempo_resposta_horas, tempo_resolucao_horas)
│   │   ├── faturamento.py       # FaturamentoHistorico — snapshots mensais por unidade
│   │   └── glosa.py             # GlosaFaixa, GlosaChamado (StatusGlosa)
│   ├── schemas/
│   │   ├── patrimonio.py
│   │   ├── usuario.py
│   │   └── movimentacao.py
│   ├── services/
│   │   ├── auth_service.py      # ES256 JWKS + HS256 fallback; login, get_usuario_logado
│   │   ├── tenant_service.py    # Onboarding — registrar_tenant (Supabase Auth + Tenant + Usuario)
│   │   ├── patrimonio_service.py# CRUD patrimonial isolado por tenant_id
│   │   ├── da_service.py        # Data Analytics — snapshot + Claude insights
│   │   ├── llm_service.py       # Assistente IA — loop agêntico tool_use + SSE streaming
│   │   ├── rbac_service.py      # RBAC — tem_permissao(), exigir(), nivel_minimo(), exigir_nivel()
│   │   ├── chamado_service.py   # Máquina de estados de chamado + buscar_ou_404 + listar
│   │   ├── config_service.py    # Configurações de serviço
│   │   ├── sla_service.py       # seed_sla_padrao() + cálculo de prazo por prioridade
│   │   ├── glosa_service.py     # abrir/encerrar/calcular glosa + seed faixas
│   │   └── storage_service.py   # Pillow compress (WebP) + sanitizar_filename + upload Supabase
│   ├── routers/
│   │   ├── auth.py              # /auth/login (seta tenant_slug cookie), /auth/logout
│   │   ├── tenant.py            # /empresa/registrar (onboarding pública)
│   │   ├── dashboard.py         # /dashboard
│   │   ├── patrimonio.py        # /patrimonio — CRUD
│   │   ├── movimentacao.py      # /movimentacao
│   │   ├── assistente.py        # /assistente — chat SSE
│   │   ├── da.py                # /da — Data Analytics
│   │   ├── cargo.py             # /cargos — CRUD
│   │   ├── filial.py            # /filiais — CRUD; DELETE → HTTP 409 se dependentes
│   │   ├── funcionario.py       # /funcionarios — soft-delete, subordinados
│   │   ├── chamado.py           # /chamados — CRUD + upload 10MB + estados
│   │   ├── peca.py              # /pecas — catálogo + upsert estoque geral/filial
│   │   ├── orcamento.py         # /orcamentos — fluxo aprovação + PDF + NF (10MB)
│   │   ├── admin.py             # /admin — painel admin: chamados, funcionários, SLA, faturamento
│   │   ├── glosa.py             # /admin/glosa — 9 rotas: CRUD + relatório + faixas
│   │   ├── tecnico.py           # /tecnico — painel técnico
│   │   └── superadmin.py        # /superadmin — gestão de tenants
│   ├── templates/
│   │   ├── base.html            # Layout Bootstrap com nav
│   │   ├── base_tecnico.html
│   │   ├── base_superadmin.html
│   │   ├── login.html           # Logo bucket Supabase + link cadastro
│   │   ├── dashboard.html
│   │   ├── admin/
│   │   │   ├── chamados.html
│   │   │   ├── funcionarios.html
│   │   │   ├── integracoes.html
│   │   │   ├── sla.html
│   │   │   ├── usuarios.html
│   │   │   ├── faturamento.html            # Tableau mês atual: calcular/fechar período
│   │   │   ├── faturamento_historico.html  # Tabela de snapshots fechados
│   │   │   ├── faturamento_relatorio.html  # Relatório matricial: unidades × meses (ano)
│   │   │   ├── dre.html                    # DRE: demonstrativo mensal + ranking + comparativo
│   │   │   ├── glosa.html                  # Glosa: lista com KPIs + filtros
│   │   │   ├── glosa_form.html             # Abertura de glosa
│   │   │   ├── glosa_detalhe.html          # Detalhe + encerramento
│   │   │   ├── glosa_relatorio.html        # Relatório por unidade + print CSS
│   │   │   └── glosa_faixas.html           # Configuração faixas percentuais
│   │   ├── patrimonio/
│   │   ├── movimentacao/
│   │   ├── assistente/
│   │   ├── da/
│   │   ├── partials/
│   │   ├── tecnico/
│   │   └── tenant/
│   ├── security/
│   │   └── audit.py
│   └── static/
│       ├── css/style.css        # Barlow (fallback Helixa), cores #ff4e17/#000/#c8c8c8/#fff
│       ├── js/
│       │   ├── main.js
│       │   ├── offline.js
│       │   ├── onboarding.js
│       │   └── sw.js
│       └── manifest.json
├── migrations/
│   ├── 001_sla_configs.sql
│   ├── 002_faturamento_historico.sql
│   └── 003_glosa_chamados.sql
├── importar_faturamento_real.py # CLI: importa FATURAMENTO.xlsx → faturamento_historico
├── importar_patrimonio.py
├── criar_usuarios_teste.py
├── seed_sla.py
├── mcp_server.py
├── supabase_schema.sql
├── .env
├── requirements.txt
└── run.py
```

---

## Banco de dados — 25 tabelas no Supabase

### Módulo base
`tenants`, `usuarios`, `patrimonios`, `movimentacoes`, `audit_logs`

### Módulo FARTECH
`cargos`, `filiais`, `funcionarios`, `chamados`, `anexos_chamado`,
`pecas`, `estoque_geral`, `estoque_filial`, `pecas_chamado`,
`orcamentos`, `aprovacoes_orcamento`, `notas_fiscais`, `sla_configs`

### Módulo Faturamento (migration 002)
`faturamento_historico`

### Módulo Glosa (migration 003)
`glosa_chamados`, `glosa_faixas`

---

## Módulo Faturamento

### Modelo `faturamento_historico`
| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL PK | — |
| `tenant_id` | UUID FK tenants | isolamento multitenant |
| `filial_id` | INTEGER FK filiais | nullable (ON DELETE SET NULL) |
| `filial_nome` | VARCHAR(150) | snapshot do nome (preservado em renomeações) |
| `mes` | SMALLINT | 1–12 |
| `ano` | SMALLINT | ≥ 2020 |
| `chamados_count` | INTEGER | qtd chamados no período |
| `valor_mao_obra` | NUMERIC(12,2) | — |
| `valor_pecas` | NUMERIC(12,2) | — |
| `valor_total` | NUMERIC(12,2) | — |
| `origem` | VARCHAR(20) | `'sistema'` (calculado) ou `'importacao'` (xlsx) |
| `arquivo_origem` | VARCHAR(255) | nome do xlsx quando origem=importacao |
| `fechado_por_id` | INTEGER FK funcionarios | nullable |
| `fechado_em` | TIMESTAMPTZ | — |

**Constraint de unicidade**: `(tenant_id, filial_nome, mes, ano, origem)`

### Rotas `/admin/faturamento` e `/admin/dre`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/admin/faturamento` | Tableau: calcular/fechar mês atual |
| POST | `/admin/faturamento/fechar` | Cria snapshots imutáveis do período |
| POST | `/admin/faturamento/reabrir` | Remove snapshots do período |
| GET | `/admin/faturamento/historico` | Lista snapshots fechados |
| GET | `/admin/faturamento/relatorio` | Relatório matricial: unidades × meses |
| GET | `/admin/dre` | **DRE** — demonstrativo mensal com comparativo ano anterior + ranking |

### Filtro Jinja2 `brl`
Registrado em `admin.py`: formata `float` → `R$ 1.234.567,89`

### Script de importação `importar_faturamento_real.py`
- **Entrada**: FATURAMENTO.xlsx (42+ abas, uma por mês no formato `out/2022`, `nov/2022`, etc.)
- **Comportamento**: idempotente — atualiza se valor mudou, ignora se igual
- **Flags**: `--dry-run`, `--desde AAAA-MM`, `--aba "NOME DA ABA"`
- **RLS**: `SET app.current_tenant_id = '{uuid}'` (inline, não bindparam — PostgreSQL não aceita $1 em SET)
- **Commits**: por aba para evitar timeout
- **Resultado**: 1.252 registros | R$ 180.565.246,58 | out/2022 → mar/2026 | 33 unidades

### DRE — `/admin/dre`
- **Template**: `admin/dre.html`
- **Filtros**: `?ano=YYYY&filial_nome=NOME` — Exercício + Unidade (dropdown com todas as 33)
- **KPIs**: Receita Total, Mão de Obra, Materiais/Peças, Chamados + ticket médio
- **Tabela**: 12 meses × [mão de obra, materiais, total atual, total ano anterior, variação %, chamados, ticket]
- **Comparativo**: automático vs ano anterior linha a linha + variação % no total anual
- **Ranking**: top-10 unidades por faturamento no ano (coluna lateral — só no consolidado)
- **Drill-down**: cada linha do ranking é link para `/admin/dre?ano=X&filial_nome=NOME`
- **Impressão**: `@media print` oculta filtros + sidebar
- **Dados 2025**: R$ 59.158.676,10 | 12 meses | 33 unidades

---

## Hierarquia de cargos
| Nível | Cargo |
|---|---|
| 1 | Diretor |
| 2 | Gerente |
| 3 | Coordenador |
| 4 | Supervisor |
| 5 | Técnico Sênior |
| 6 | Técnico |
| 7 | Auxiliar |

---

## Arquitetura Multitenant

### Isolamento de dados
Toda tabela de negócio tem `tenant_id` e todas as queries filtram por ele.

### Resolução de tenant (TenantMiddleware)
```
Request → TenantMiddleware → request.state.tenant_slug
  1. Subdomínio:   emtel.polsec.app → slug = "emtel"
  2. Header:       X-Tenant-Slug: emtel
  3. Cookie:       tenant_slug=emtel  ← setado automaticamente no login (dev/localhost)
```

---

## Autenticação (Supabase Auth — ES256)

```
Login → Supabase → access_token (JWT ES256) + refresh_token
      → Cookie httponly access_token + Cookie tenant_slug (do user_metadata.slug)

Request → get_usuario_logado():
  1. Lê cookie access_token
  2. decodificar_token():
     - lê header alg do JWT
     - ES256: busca chave pública via JWKS /auth/v1/.well-known/jwks.json (cached @lru_cache)
     - HS256: fallback com SUPABASE_JWT_SECRET (legado)
  3. Extrai supabase_uid do payload
  4. Resolve tenant via request.state.tenant_slug
  5. Consulta Usuario WHERE supabase_uid = ? AND tenant_id = tenant.id AND ativo = True
  6. Retorna Usuario ou 303 → /auth/login
```

---

## Módulo Storage

- **Bucket**: `polsec-anexos` (Supabase Storage)
- **Estrutura de path**: `{tenant_slug}/chamados/{chamado_id}/{tipo}/{arquivo_sanitizado}`
- **Tipos**: `fotos/`, `orcamentos/`, `notas_fiscais/`, `laudos/`, `outros/`
- **Compressão imagens**: Pillow → WebP, max 1920px, qualidade 75
- **Segurança**: `sanitizar_filename()` — `os.path.basename` + regex `[^\w.\-]` → OWASP A03
- **Limite de upload**: 10 MB em todos os endpoints (HTTP 413 se excedido)

---

## Módulo Chamados — Máquina de Estados

```
aberto → em_atendimento → aguardando_pecas → em_execucao
       → concluido | cancelado | reaberto
```

---

## Módulo Orçamentos — Fluxo de Aprovação

```
rascunho → aguardando_aprovacao → aprovado | rejeitado | cancelado
```
- `AprovacaoOrcamento` registra cada transição (audit trail imutável)
- Todos os commits são atômicos

---

## Módulo SLA

- **Tabela**: `sla_configs` (prioridade, tempo_resposta_horas, tempo_resolucao_horas)
- **Seed**: `seed_sla_padrao()` em `sla_service.py`
- **Gestão**: `/admin/sla` — editar tempos por prioridade

---

## RBAC

- **Modelo**: `Cargo.permissoes` (JSON) + `nivel_hierarquico` (1-7)
- **Service**: `rbac_service.py` — `tem_permissao(func, modulo, acao)`, `exigir()`, `exigir_nivel()`

---

## Módulo Glosa (migration 003)

### Tabelas adicionadas
| Tabela | Descrição |
|---|---|
| `glosa_chamados` | Registro de períodos de indisponibilidade com cálculo de penalidade |
| `glosa_faixas` | Faixas de percentual de glosa por tempo de indisponibilidade |

### Colunas novas em `chamados`
`numero_chamado` (INTEGER), `tipo_chamado` (VARCHAR20: `preventiva`\|`corretiva`), `data_chegada_tecnico` (TIMESTAMPTZ), `justificativa_atraso` (TEXT), `codigo_unidade` (VARCHAR10)

### Faixas padrão Polsec (seed)
| Horas | Percentual |
|---|---|
| 1 – 24h | 2% |
| 24 – 60h | 4% |
| 60 – 168h | 8% |
| 168 – 240h | 16% |
| > 240h | 32% |

### Rotas `/admin/glosa`
| Método | Rota | Descrição |
|---|---|---|
| GET | `/admin/glosa/` | Lista com KPIs (ativas/encerradas/contestadas/canceladas) + filtros + paginação |
| GET | `/admin/glosa/novo` | Formulário abertura de glosa |
| POST | `/admin/glosa/novo` | Abre glosa (status='ativa') |
| GET | `/admin/glosa/{id}` | Detalhe + encerramento |
| POST | `/admin/glosa/{id}/encerrar` | Calcula horas + % + valor_glosa |
| POST | `/admin/glosa/{id}/cancelar` | Cancela glosa |
| GET | `/admin/glosa/relatorio/periodo` | Relatório agregado por unidade (ano/mês) |
| GET | `/admin/glosa/faixas/config` | Configuração das faixas |
| POST | `/admin/glosa/faixas/seed` | Insere faixas padrão Polsec |

### Service `glosa_service.py`
- `calcular_horas(inicio, fim)` → Decimal
- `calcular_percentual(horas, tenant_id, db)` → Decimal
- `abrir_glosa(...)` → GlosaChamado com status='ativa'
- `encerrar_glosa(id, data_fim, ...)` → calcula automaticamente horas + % + valor_glosa
- `listar_glosas(...)` → paginação + filtros
- `resumo_glosa_periodo(tenant_id, db, ano, mes)` → agrega por filial

### StatusGlosa (enum)
`ativa` | `encerrada` | `contestada` | `cancelada`

---

## Módulo IA — Assistente

- **Rota**: `GET /assistente/` → `POST /assistente/chat`
- **Modelo**: `claude-opus-4-6` com `thinking: {type: "adaptive"}`
- **Transport**: SSE (`text/event-stream`)
- **Ferramentas** (9 tools isoladas por tenant_id):
  - `buscar_patrimonios`, `obter_estatisticas`, `listar_movimentacoes`, `buscar_patrimonio_por_codigo` _(originais)_
  - `consultar_faturamento`, `estatisticas_faturamento` _(faturamento histórico)_
  - `listar_chamados`, `listar_filiais`, `resumo_geral` _(chamados, unidades, visão consolidada)_

---

## Módulo IA — Data Analytics

- **Rota**: `GET /da/` → `POST /da/analisar`
- **Saída JSON estruturada**: `resumo_executivo`, `indicadores_chave`, `alertas`, `insights`, `recomendacoes`, `score_gestao`

---

## Módulo MCP

- **Arquivo**: `mcp_server.py` (FastMCP, porta 8001)
- **Tools**: `listar_patrimonios`, `obter_estatisticas`, `buscar_por_codigo`, `listar_movimentacoes`, `listar_setores`
- **Resource**: `patrimonio://acervo/resumo`

---

## Variáveis de ambiente (.env)

```env
DATABASE_URL=postgresql+psycopg://...
SUPABASE_URL=https://<id>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=...        # usado apenas para fallback HS256
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Tenants de referência

| Campo | FARTECH (dev) | POLSEC (prod/demo) |
|---|---|---|
| Nome | FARTECH | POLSEC / GRUPO EMTEL |
| Slug | `fartech` | `polsec` |
| UUID | — | `dd3ce17e-b506-46cf-9cce-707b20d1e253` |
| E-mail admin | `contato@fartech.app.br` | — |

### Filiais POLSEC (unidades prisionais — 33 ativas)
Importadas do FATURAMENTO.xlsx. Exemplos: PEP I FRANCO DA ROCHA, CDP SÃO PAULO, CPPL I, etc.
Nenhum funcionário cadastrado (banco limpo — só dados reais de faturamento e patrimônio).

### Dados reais POLSEC
| Tabela | Registros |
|---|---|
| `faturamento_historico` (origem=importacao) | 1.252 |
| `patrimonios` | 8.009 |
| `filiais` | 33 |

---

## Dashboard (`/dashboard`)

### Variáveis injetadas pelo `dashboard.py`
| Variável | Tipo | Descrição |
|---|---|---|
| `fat_total_hist` | float | Soma histórica total de faturamento |
| `ultimo_fat` | Row\|None | `.mes`, `.ano`, `.total`, `.unidades` |
| `chamados_abertos` | int | Count status=aberto |
| `chamados_em_atendimento` | int | Count status=em_atendimento |
| `total_filiais` | int | Count filiais do tenant |
| `total` | int | Total de patrimônios |
| `status_map` | dict | Contagens por status |
| `por_setor` | list | Top setores (tuples nome, qty) |

### Layout `dashboard.html`
- **Linha 1**: Faturamento histórico total · Último mês fechado · Unidades prisionais · Chamados em aberto
- **Linha 2**: Total bens · Ativos · Manutenção · Extraviados
- **Rodapé**: Bens por Setor (barras) + Status do Acervo (lista) + indicadores de faturamento

---

## Comandos úteis

```bash
cd backend
source .venv/bin/activate
python run.py                   # porta 8000

python mcp_server.py            # porta 8001 (MCP)

# Importar planilha de faturamento
python importar_faturamento_real.py /path/to/FATURAMENTO.xlsx --tenant polsec
python importar_faturamento_real.py /path/to/FATURAMENTO.xlsx --tenant polsec --dry-run
python importar_faturamento_real.py /path/to/FATURAMENTO.xlsx --tenant polsec --desde 2025-01
```

---

## URLs locais

| URL | Descrição |
|---|---|
| http://localhost:8000/auth/login | Login |
| http://localhost:8000/empresa/registrar | Onboarding nova empresa |
| http://localhost:8000/dashboard | KPIs (auth) |
| http://localhost:8000/patrimonio | Patrimônio (auth) |
| http://localhost:8000/assistente | Chat IA (auth) |
| http://localhost:8000/da | Data Analytics (auth) |
| http://localhost:8000/admin/faturamento | Faturamento — fechar período (auth admin) |
| http://localhost:8000/admin/faturamento/relatorio | Relatório matricial anual (auth admin) |
| http://localhost:8000/admin/dre | DRE — demonstrativo mensal + ranking (auth admin) |
| http://localhost:8000/docs | Swagger UI |

---

## Identidade Visual — Manual POLSEC (Quartel Design, 2025)

### Paleta de cores

| Token CSS | HEX | Pantone | Uso |
|---|---|---|---|
| `--polsec-orange` | `#ff4e17` | Orange 021 C | Primário — CTAs, destaques, nav ativa |
| `--polsec-black` | `#000000` | — | Sidebar, fundos escuros |
| `--polsec-gray` | `#c8c8c8` | — | Textos secundários, bordas |
| `--polsec-white` | `#ffffff` | — | Fundos claros, texto sobre escuro |

### Tipografia

- **Família primária**: Helixa (Light / Regular / Bold) — fonte comercial Latinotype
- **Fallback web**: **Barlow** (Google Fonts, pesos 300/400/700)
- `font-family: 'Helixa', 'Barlow', system-ui, sans-serif`

### Logo na tela de login
```
https://nolchmlmkebfuiamxvml.supabase.co/storage/v1/object/public/POLSEC%20IMAGES/PNG/POLSEC_MARCA_Artboard%201%20copy%2012.png
```

### CSS base

```css
:root {
  --polsec-orange:  #ff4e17;
  --polsec-black:   #000000;
  --polsec-gray:    #c8c8c8;
  --polsec-white:   #ffffff;
  --font-brand: 'Helixa', 'Barlow', system-ui, sans-serif;
}
```

---

## Histórico de commits

| Hash | Descrição |
|---|---|
| `fcbc0a8` | feat: setup inicial POLSEC |
| `c7c4cc2` | fix: 10 bugs críticos (code review sênior) |
| `b49a411` | feat: módulos FARTECH — funcionários, chamados, estoque, orçamentos, storage |
| `f8857e0` | fix: 12 bugs críticos — security, data integrity, OOM, isolamento |
| `9ffc5b9` | fix: login ES256 JWKS + cookie tenant_slug |
| `a6ecc50` | style: fonte Barlow substitui Inter |
| `9eabd2c` | style: logo POLSEC na tela de login (bucket Supabase) |
| —         | feat: módulo faturamento — model, migration 002, rotas admin, relatório matricial |
| —         | feat: importar_faturamento_real.py — 1.252 registros EMTEL importados (out/2022→mar/2026) |
| —         | fix: debug tela a tela — FARTECH→POLSEC, anos_disponiveis desde 2022, usuarios.html |
| —         | feat: dashboard expandido — KPIs faturamento/chamados/filiais (dashboard.py + dashboard.html) |
| —         | feat: llm_service.py — 9 ferramentas (era 4): faturamento, chamados, filiais, resumo_geral |
| —         | feat: DRE /admin/dre — demonstrativo mensal, comparativo anual, ranking top-10, drill-down |

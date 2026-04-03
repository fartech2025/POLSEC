# POLSEC — Sistema de Gestão Patrimonial SaaS
## Arquitetura Canônica (atualizado 2026-04-03)

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI 0.111 + Python 3.12 |
| Templates | Jinja2 + Bootstrap 5.3 (SSR, sem SPA) |
| ORM | SQLAlchemy 2.0 (psycopg3) |
| Banco local | PostgreSQL 16 — `emtel_patrimonial` @ localhost:5432 |
| Banco prod | Supabase PostgreSQL (connection pooler, porta 6543) |
| Auth | Supabase Auth — JWT HS256 via cookie `access_token` |
| IA | Claude claude-opus-4-6 — tool_use agentico + SSE streaming |
| Análise | Claude claude-opus-4-6 — Data Analytics com adaptive thinking |
| MCP | FastMCP — servidor standalone para Claude Desktop |

---

## Estrutura do projeto

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + middleware + routers
│   ├── config.py                # Pydantic Settings — lê .env
│   ├── database.py              # Engine SQLAlchemy + get_db() + get_db_with_tenant()
│   ├── middleware/
│   │   └── tenant.py            # TenantMiddleware — resolve slug por subdomínio > header > cookie
│   ├── models/
│   │   ├── tenant.py            # Tenant (id UUID, slug, nome, plano, ativo)
│   │   ├── usuario.py           # Usuario (supabase_uid, tenant_id, perfil)
│   │   ├── patrimonio.py        # Patrimonio (tenant_id, codigo, status)
│   │   ├── movimentacao.py      # Movimentacao (tenant_id, tipo, dados_anteriores/novos)
│   │   └── audit_log.py         # AuditLog (tenant_id, acao, tabela, dados)
│   ├── schemas/
│   │   ├── patrimonio.py        # PatrimonioCreate / PatrimonioUpdate
│   │   ├── usuario.py
│   │   └── movimentacao.py
│   ├── services/
│   │   ├── auth_service.py      # Supabase Auth — login, JWT decode, get_usuario_logado, requer_perfil
│   │   ├── tenant_service.py    # Onboarding — registrar_tenant (Supabase Auth + Tenant + Usuario)
│   │   ├── patrimonio_service.py# CRUD patrimonial isolado por tenant_id
│   │   ├── da_service.py        # Data Analytics — snapshot + Claude insights (JSON estruturado)
│   │   └── llm_service.py       # Assistente IA — loop agentico tool_use + SSE streaming
│   ├── routers/
│   │   ├── auth.py              # /auth/login, /auth/logout
│   │   ├── tenant.py            # /empresa/registrar (onboarding pública)
│   │   ├── dashboard.py         # /dashboard — agregados por tenant
│   │   ├── patrimonio.py        # /patrimonio — CRUD completo
│   │   ├── movimentacao.py      # /movimentacao — histórico
│   │   ├── assistente.py        # /assistente — chat SSE com Claude
│   │   └── da.py                # /da — Data Analytics (POST /analisar → JSON)
│   ├── templates/
│   │   ├── base.html            # Layout Bootstrap com nav (Dashboard, Patrimônio, IA, DA)
│   │   ├── login.html           # Página de login + link de cadastro
│   │   ├── dashboard.html       # KPIs + gráficos
│   │   ├── patrimonio/          # lista.html, form.html, detalhe.html
│   │   ├── movimentacao/        # lista.html
│   │   ├── assistente/          # chat.html (SSE reader + atalhos)
│   │   ├── da/                  # painel.html (score + alertas + insights)
│   │   └── tenant/              # registrar.html, sucesso.html
│   └── static/
│       └── css/style.css
├── mcp_server.py                # FastMCP server standalone (5 tools + 1 resource)
├── supabase_schema.sql          # DDL completo + RLS policies para Supabase
├── .env                         # Variáveis de ambiente (não versionar)
├── .env.example                 # Template documentado
├── requirements.txt
└── run.py                       # uvicorn app.main:app --reload
```

---

## Arquitetura Multitenant

### Isolamento de dados
Cada tabela de negócio (`usuarios`, `patrimonios`, `movimentacoes`, `audit_logs`) tem:
- `tenant_id VARCHAR(36)` — FK para `tenants.id`
- Todas as queries filtram por `tenant_id` no service layer

### Resolução de tenant (TenantMiddleware)
```
Request → TenantMiddleware → request.state.tenant_slug
  1. Subdomínio:   emtel.polsec.app → slug = "emtel"
  2. Header:       X-Tenant-Slug: emtel
  3. Cookie:       tenant_slug=emtel (fallback dev)
```

### Autenticação (Supabase Auth)
```
Login → Supabase → access_token (JWT HS256) → Cookie httponly
Request → get_usuario_logado():
  1. Lê cookie access_token
  2. decode JWT com SUPABASE_JWT_SECRET → supabase_uid
  3. Consulta Usuario WHERE supabase_uid = ? AND tenant_id = tenant.id
  4. Retorna Usuario ou redireciona para /auth/login
```

### RLS no Supabase (produção)
```sql
-- Variável de sessão setada pelo backend em cada request:
SET LOCAL app.current_tenant_id = '<uuid>';

-- Política RLS em todas as tabelas:
CREATE POLICY tenant_isolation ON patrimonios
    USING (tenant_id = current_tenant_id());
```

### Perfis de usuário
| Perfil | Acesso |
|---|---|
| `administrador` | Tudo, incluindo gestão de usuários |
| `operador` | CRUD patrimônios e movimentações |
| `visualizador` | Somente leitura |

---

## Fluxo de onboarding

```
/empresa/registrar (pública)
  → tenant_service.registrar_tenant()
    1. Valida slug único
    2. registrar_usuario_supabase() → supabase_uid (service_role)
    3. INSERT tenants (id=uuid4, slug, nome, plano)
    4. INSERT usuarios (supabase_uid, tenant_id, perfil=administrador)
  → /tenant/sucesso.html
  → Usuário faz login em /auth/login
```

---

## Módulo IA — Assistente

- **Rota**: `GET /assistente/` → `POST /assistente/chat`
- **Modelo**: `claude-opus-4-6` com `thinking: {type: "adaptive"}`
- **Loop agentico**: enquanto `stop_reason == "tool_use"`, executa ferramentas e reenvia
- **Transport**: SSE (`text/event-stream`) — eventos `tipo: texto|ferramenta|fim`
- **Ferramentas** (4 tools, isoladas por tenant_id):
  - `buscar_patrimonios` — com filtros de busca, setor, status
  - `obter_estatisticas` — totais, por status, top setores
  - `listar_movimentacoes` — histórico com filtro por patrimônio
  - `buscar_patrimonio_por_codigo` — detalhe completo

## Módulo IA — Data Analytics

- **Rota**: `GET /da/` → `POST /da/analisar`
- **Modelo**: `claude-opus-4-6` com `thinking: {type: "adaptive"}`
- **Fluxo**: `coletar_dados_analiticos()` → prompt com JSON do acervo → Claude → parse JSON
- **Saída estruturada**:
  ```json
  {
    "resumo_executivo": "...",
    "indicadores_chave": [...],
    "alertas": [{"nivel": "critico|atencao|info", ...}],
    "insights": [...],
    "recomendacoes": [...],
    "score_gestao": {"nota": 0-100, ...}
  }
  ```

## Módulo MCP

- **Arquivo**: `mcp_server.py` (FastMCP, porta 8001)
- **Uso**: integração com Claude Desktop (adicionar em `claude_desktop_config.json`)
- **Tools**: `listar_patrimonios`, `obter_estatisticas`, `buscar_por_codigo`, `listar_movimentacoes`, `listar_setores`
- **Resource**: `patrimonio://acervo/resumo`

---

## Variáveis de ambiente (.env)

```env
DATABASE_URL=postgresql+psycopg://...       # Local ou Supabase pooler
SUPABASE_URL=https://<id>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=...                     # Settings > API > JWT Secret
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Comandos úteis

```bash
# Ativar ambiente e subir servidor
cd backend
source .venv/bin/activate      # ou .venv/bin/activate.fish / .venv/Scripts/activate
python run.py                  # uvicorn na porta 8000

# MCP server (porta 8001)
python mcp_server.py

# Aplicar schema no Supabase
# SQL Editor do projeto → colar conteúdo de supabase_schema.sql

# Verificar servidor
curl http://localhost:8000/auth/login
```

---

## Dev local sem Supabase

Para desenvolvimento local sem credenciais Supabase reais:

1. O servidor inicia normalmente (Supabase client é lazy via `@lru_cache`)
2. As páginas públicas funcionam: `/auth/login`, `/empresa/registrar`
3. Login e rotas autenticadas precisam de `SUPABASE_URL` + `SUPABASE_ANON_KEY` reais
4. Para criar um projeto Supabase gratuito: [supabase.com/dashboard](https://supabase.com/dashboard)
5. Após configurar credenciais: executar `supabase_schema.sql` no SQL Editor

---

## URLs locais

| URL | Descrição |
|---|---|
| http://localhost:8000 | Redireciona para /dashboard |
| http://localhost:8000/auth/login | Login |
| http://localhost:8000/empresa/registrar | Onboarding de nova empresa |
| http://localhost:8000/dashboard | KPIs (requer auth) |
| http://localhost:8000/patrimonio | Lista de bens (requer auth) |
| http://localhost:8000/assistente | Chat com Claude (requer auth) |
| http://localhost:8000/da | Data Analytics (requer auth) |
| http://localhost:8000/docs | Swagger UI (FastAPI auto-docs) |

---

## Identidade Visual — Manual POLSEC

> Fonte: Manual de Diretrizes Visuais POLSEC (Quartel Design, 2025).
> Todos os componentes de UI devem seguir estritamente esta seção.

### Paleta de cores

| Token CSS | Valor HEX | Pantone | Uso |
|---|---|---|---|
| `--polsec-orange` | `#ff4e17` | Orange 021 C | Cor primária — CTAs, destaques, ativo na nav |
| `--polsec-black` | `#000000` | — | Backgrounds escuros, sidebar |
| `--polsec-gray` | `#c8c8c8` | — | Textos secundários, bordas suaves |
| `--polsec-white` | `#ffffff` | — | Fundos claros, texto sobre escuro |

CMYK de referência para impressão:
- Laranja: `C0 M84 Y98 K0` / RGB `255 78 23`
- Preto: `C20 M20 Y20 K100` / RGB `0 0 0`

### Tipografia

- **Família primária**: Helixa (Light / Regular / Bold)
- **Fallback web**: Inter (Google Fonts) → `system-ui` → `sans-serif`
- `font-family: 'Helixa', 'Inter', system-ui, sans-serif`
- Todas as iniciais de marca em **caixa alta** com `letter-spacing` amplo

### Versões do logotipo

| Versão | Uso |
|---|---|
| Horizontal (símbolo + wordmark) | Uso padrão — sidebar, cabeçalhos |
| Vertical (símbolo sobre wordmark) | Materiais quadrados, avatares amplos |
| Símbolo isolado | Favicon, ícone de app, sidebar colapsada |
| Tipografia isolada | Contextos onde símbolo não cabe |

### Regras de aplicação de cor

Combinações **permitidas**:
- Fundo branco → marca preta
- Fundo preto → marca branca
- Fundo laranja `#ff4e17` → marca preta
- Fundo branco → marca laranja `#ff4e17`
- Fundo preto → marca laranja `#ff4e17`
- Fundo laranja → marca branca

Combinações **proibidas**: qualquer fundo fora de `#ffffff`, `#000000` ou `#ff4e17`; gradientes que não pertençam à cartela; cores externas (azul, magenta, amarelo, etc.).

### Usos proibidos da marca

- Inclinação, rotação ou espelhamento
- Distorção ou achatamento do símbolo
- Redisposição texto/símbolo (ex.: wordmark antes do símbolo)
- Desalinhamento vertical entre símbolo e wordmark
- Acréscimo de borda, sombra ou opacidade reduzida
- Cores fora da paleta oficial

### Margem de segurança

A margem mínima ao redor do logotipo é `X`, onde `X` = altura do símbolo. Nenhum elemento externo pode invadir essa área.

### Aplicação no CSS (`static/css/style.css`)

```css
:root {
  --polsec-orange:  #ff4e17;   /* primário */
  --polsec-black:   #000000;   /* sidebar, fundos escuros */
  --polsec-gray:    #c8c8c8;   /* textos secundários */
  --polsec-white:   #ffffff;   /* fundos claros */
  --font-brand: 'Helixa', 'Inter', system-ui, sans-serif;
}
```

Classes utilitárias da marca:
- `.btn-brand` / `.btn-outline-brand` — botões primários laranja
- `.sidebar-brand` — wordmark na sidebar (uppercase, letter-spacing)
- `.sidebar-section-label` — rótulos de seção (uppercase, micro)
- `.login-brand` — wordmark na tela de login
- `.login-body` — gradiente `#000 → #1a0a00 → #ff4e17`


from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import logging

from app.config import settings
from app.database import Base, engine
from app.middleware.tenant import TenantMiddleware
from app.routers import auth, patrimonio, movimentacao, dashboard, assistente, da
from app.routers import tenant, superadmin, tecnico, admin
from app.routers import cargo, filial, funcionario, chamado, peca, orcamento

logger = logging.getLogger(__name__)

# Cria tabelas apenas se DATABASE_URL estiver configurado
if settings.DATABASE_URL:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Não foi possível criar tabelas no banco: %s", exc)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(TenantMiddleware)

# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
app.include_router(tenant.router, prefix="/empresa", tags=["Empresa"])
app.include_router(patrimonio.router, prefix="/patrimonio", tags=["Patrimônio"])
app.include_router(movimentacao.router, prefix="/movimentacao", tags=["Movimentação"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(assistente.router, prefix="/assistente", tags=["Assistente IA"])
app.include_router(da.router, prefix="/da", tags=["Data Analytics"])

app.include_router(superadmin.router, prefix="/superadmin", tags=["SuperAdmin"])
app.include_router(tecnico.router, prefix="/tecnico", tags=["Técnico"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

# ── Módulos FARTECH ───────────────────────────────────────────────────────────
app.include_router(cargo.router, prefix="/cargos", tags=["Cargos"])
app.include_router(filial.router, prefix="/filiais", tags=["Filiais"])
app.include_router(funcionario.router, prefix="/funcionarios", tags=["Funcionários"])
app.include_router(chamado.router, prefix="/chamados", tags=["Chamados"])
app.include_router(peca.router, prefix="/pecas", tags=["Peças & Estoque"])
app.include_router(orcamento.router, prefix="/orcamentos", tags=["Orçamentos"])


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

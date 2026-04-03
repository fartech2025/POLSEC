from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import Base, engine
from app.middleware.tenant import TenantMiddleware
from app.routers import auth, patrimonio, movimentacao, dashboard, assistente, da
from app.routers import tenant

Base.metadata.create_all(bind=engine)

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


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

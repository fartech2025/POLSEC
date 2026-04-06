import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import Base, engine
from app.middleware.rate_limit import LoginRateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
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


# ── Auditoria de segurança diária (2h) ───────────────────────────────────────

_AUDIT_HOUR = 2  # hora do dia (0-23) para executar a varredura


async def _daily_audit_loop() -> None:
    """Agendador assíncrono: executa a auditoria de segurança diariamente às _AUDIT_HOUR:00."""
    while True:
        agora = datetime.now()
        alvo = agora.replace(hour=_AUDIT_HOUR, minute=0, second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
        await asyncio.sleep((alvo - agora).total_seconds())
        try:
            from app.security.audit import executar_auditoria
            await asyncio.to_thread(executar_auditoria)
        except Exception as exc:
            logger.error("Falha na auditoria de segurança diária: %s", exc)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    audit_task = asyncio.create_task(_daily_audit_loop())
    logger.info(
        "Auditoria de segurança agendada para %02d:00 diariamente",
        _AUDIT_HOUR,
    )
    yield
    audit_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await audit_task


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    # Docs visíveis apenas em modo DEBUG (ocultar em produção reduz superfície de ataque)
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (ordem: último adicionado = mais externo = primeiro a processar) ──
app.add_middleware(TenantMiddleware)           # innermost: resolve tenant
app.add_middleware(SecurityHeadersMiddleware)  # middle:    injeta headers de segurança
app.add_middleware(LoginRateLimitMiddleware)   # outermost: bloqueia brute-force antes de tudo

# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── PWA: Service Worker e Manifest (devem ficar na raiz) ─────────────────────
@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        "app/static/js/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )

@app.get("/manifest.json", include_in_schema=False)
async def pwa_manifest():
    return FileResponse(
        "app/static/manifest.json",
        media_type="application/manifest+json",
    )

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

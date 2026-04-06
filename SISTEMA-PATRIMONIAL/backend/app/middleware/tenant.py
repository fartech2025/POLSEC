"""
TenantMiddleware
Extrai o tenant a partir do subdomínio ou header X-Tenant-Slug.

Estratégia de resolução (em ordem):
  1. Subdomínio: emtel.polsec.app → slug = "emtel"
  2. Header:     X-Tenant-Slug: emtel
  3. Cookie:     tenant_slug=emtel  (fallback dev)
"""
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_IP_RE = re.compile(r'^\d{1,3}(\.\d{1,3}){3}(:\d+)?$')


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        slug = self._resolver_slug(request)
        request.state.tenant_slug = slug
        return await call_next(request)

    def _resolver_slug(self, request: Request) -> str | None:
        host = request.headers.get("host", "")

        # 1. Subdomínio — ignora hosts IP (localhost dev) e localhost puro
        if not _IP_RE.match(host) and not host.startswith("localhost"):
            partes = host.split(".")
            if len(partes) >= 3:
                candidato = partes[0]
                if candidato not in ("www", "app", "api"):
                    return candidato

        # 2. Header customizado (útil em dev e API)
        if slug := request.headers.get("x-tenant-slug"):
            return slug

        # 3. Cookie de sessão
        if slug := request.cookies.get("tenant_slug"):
            return slug

        return None

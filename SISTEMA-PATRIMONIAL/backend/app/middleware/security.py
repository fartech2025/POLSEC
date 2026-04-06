"""
SecurityHeadersMiddleware
Injeta cabeçalhos de segurança em todas as respostas HTTP. Nível bancário.

Cobre OWASP Top 10 itens:
  A05 — Security Misconfiguration  (headers ausentes)
  A03 — Injection / XSS            (CSP + X-XSS-Protection)
  A04 — Insecure Design            (HSTS, X-Frame-Options)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Content-Security-Policy calibrado para Bootstrap CDN + Google Fonts.
# 'unsafe-inline' em script/style é necessário para o bootstrap e snippets inline existentes;
# para eliminá-lo seria preciso refatorar todos os templates com nonces.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
    "img-src 'self' data: https: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self';"
)

# Caminhos que podem ser cacheados (assets estáticos)
_CACHE_OK = ("/static/", "/sw.js", "/manifest.json", "/favicon")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # ── Anti-MIME-sniffing ────────────────────────────────────────────────
        response.headers["X-Content-Type-Options"] = "nosniff"

        # ── Clickjacking ─────────────────────────────────────────────────────
        response.headers["X-Frame-Options"] = "DENY"

        # ── Reflected XSS (browsers legados) ─────────────────────────────────
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # ── Referrer ─────────────────────────────────────────────────────────
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ── Permissions ──────────────────────────────────────────────────────
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        # ── Content Security Policy ───────────────────────────────────────────
        response.headers["Content-Security-Policy"] = _CSP

        # ── HSTS — apenas sobre HTTPS ─────────────────────────────────────────
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # ── Cache-Control — desativa cache em páginas autenticadas ────────────
        path = request.url.path
        if not any(path.startswith(p) for p in _CACHE_OK):
            response.headers.setdefault(
                "Cache-Control",
                "no-store, no-cache, must-revalidate, private",
            )
            response.headers.setdefault("Pragma", "no-cache")

        return response

"""
LoginRateLimitMiddleware
Proteção contra força bruta em POST /auth/login.

Regras:
  - Máximo _MAX_ATTEMPTS tentativas por IP em janela deslizante de _WINDOW segundos
  - Após exceder: resposta 429 até a janela se esgotar naturalmente
  - Login bem-sucedido: zera o contador do IP
  - Contador em memória — reinicia com o servidor (suficiente para prevenir ataques
    de forma bruta; para persistência entre restarts, use Redis)

OWASP A07 — Identification and Authentication Failures
"""
import time
import logging
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

_log = logging.getLogger("polsec.security.ratelimit")

_WINDOW: int = 15 * 60    # 15 minutos (segundos)
_MAX_ATTEMPTS: int = 5    # tentativas antes de bloquear

# {ip: [timestamp, timestamp, ...]}
_tentativas: dict[str, list[float]] = defaultdict(list)


# ── API pública (usada pelo router auth.py) ───────────────────────────────────

def get_ip_from_request(request: Request) -> str:
    """Extrai IP real considerando proxies reversos confiáveis."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def registrar_falha_login(ip: str) -> None:
    """Chame quando um POST /auth/login falhar (senha errada, usuário inexistente)."""
    agora = time.time()
    _tentativas[ip].append(agora)
    _purgar(ip, agora)
    qtd = len(_tentativas[ip])
    _log.warning("LOGIN_FAIL ip=%s tentativas=%d/%d", ip, qtd, _MAX_ATTEMPTS)
    if qtd >= _MAX_ATTEMPTS:
        _log.error(
            "LOGIN_BLOCKED ip=%s — %d falhas em %d min",
            ip, qtd, _WINDOW // 60,
        )


def registrar_sucesso_login(ip: str) -> None:
    """Chame após login bem-sucedido para zerar o contador do IP."""
    _tentativas.pop(ip, None)


def ip_bloqueado(ip: str) -> bool:
    """Retorna True se o IP ultrapassou o limite de tentativas na janela atual."""
    agora = time.time()
    _purgar(ip, agora)
    return len(_tentativas[ip]) >= _MAX_ATTEMPTS


def _purgar(ip: str, agora: float) -> None:
    """Remove timestamps fora da janela deslizante."""
    corte = agora - _WINDOW
    _tentativas[ip] = [t for t in _tentativas[ip] if t > corte]


# ── Middleware ────────────────────────────────────────────────────────────────

class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Bloqueia POSTs para /auth/login quando o IP está na lista de bloqueio."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "POST" and request.url.path == "/auth/login":
            ip = get_ip_from_request(request)
            if ip_bloqueado(ip):
                return HTMLResponse(
                    content=_HTML_BLOQUEADO,
                    status_code=429,
                    headers={"Retry-After": str(_WINDOW)},
                )
        return await call_next(request)


_HTML_BLOQUEADO = """\
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Acesso Bloqueado — POLSEC</title>
<style>
  body{font-family:sans-serif;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;background:#f8f9fa}
  .card{text-align:center;padding:2.5rem;border-radius:10px;background:#fff;
        box-shadow:0 2px 20px rgba(0,0,0,.12);max-width:420px}
  h1{color:#dc3545;margin-bottom:.5rem;font-size:1.5rem}
  p{color:#6c757d;margin:.5rem 0}
  small{color:#adb5bd}
</style></head>
<body><div class="card">
  <h1>&#128274; Acesso Temporariamente Bloqueado</h1>
  <p>Muitas tentativas de login sem sucesso.</p>
  <p>Aguarde <strong>15 minutos</strong> e tente novamente.</p>
  <small>Se você esqueceu sua senha, entre em contato com o administrador.</small>
</div></body></html>"""

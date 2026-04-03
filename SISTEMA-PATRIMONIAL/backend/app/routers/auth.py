from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.services.auth_service import login_com_supabase, logout_supabase

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Em produção (DEBUG=False) os cookies exigem HTTPS
_SECURE_COOKIE = not settings.DEBUG


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    # Limpa cookies antigos ao exibir a página de login (troca de usuário)
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("tenant_slug")
    return response


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        tokens = login_com_supabase(email, senha)
    except Exception as exc:
        import logging
        logging.getLogger("polsec.auth").error("Falha login %s: %s", email, exc)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "E-mail ou senha incorretos."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Extrai o tenant slug dos metadados do token (sem verificar assinatura — já verificado acima)
    from jose import jwt as _jwt
    _claims = _jwt.get_unverified_claims(tokens["access_token"])
    tenant_slug = (
        _claims.get("user_metadata", {}).get("slug")
        or _claims.get("slug")
    )

    # Fallback: se o Supabase não emitiu o slug no JWT, busca pelo supabase_uid no banco
    if not tenant_slug:
        supabase_uid = _claims.get("sub")
        if supabase_uid:
            usuario = db.query(Usuario).filter(
                Usuario.supabase_uid == supabase_uid,
                Usuario.ativo == True,
            ).first()
            if usuario:
                t = db.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
                if t:
                    tenant_slug = t.slug

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=3600,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    if tenant_slug:
        response.set_cookie(
            key="tenant_slug",
            value=tenant_slug,
            httponly=False,   # lido pelo middleware sem JS
            secure=_SECURE_COOKIE,
            samesite="lax",
            max_age=7 * 24 * 3600,
        )
    return response


@router.get("/logout")
def logout(request: Request):
    token = request.cookies.get("access_token")
    if token:
        try:
            logout_supabase(token)
        except Exception:
            pass
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

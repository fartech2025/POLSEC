from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.auth_service import login_com_supabase, logout_supabase

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Em produção (DEBUG=False) os cookies exigem HTTPS
_SECURE_COOKIE = not settings.DEBUG


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        tokens = login_com_supabase(email, senha)
    except Exception:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "E-mail ou senha incorretos."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

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

"""
Router de Tenant — registro de novas empresas (onboarding).
"""
import re
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.tenant_service import registrar_tenant

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$")


@router.get("/registrar", response_class=HTMLResponse)
def registro_page(request: Request):
    return templates.TemplateResponse("tenant/registrar.html", {"request": request})


@router.post("/registrar")
def registrar(
    request: Request,
    nome_empresa: str = Form(...),
    slug: str = Form(...),
    email_admin: str = Form(...),
    senha_admin: str = Form(...),
    nome_admin: str = Form(...),
    db: Session = Depends(get_db),
):
    slug = slug.lower().strip()

    if not _SLUG_RE.match(slug):
        return templates.TemplateResponse(
            "tenant/registrar.html",
            {
                "request": request,
                "erro": "Identificador inválido. Use apenas letras minúsculas, números e hífens (3-50 caracteres).",
                "form": {
                    "nome_empresa": nome_empresa,
                    "slug": slug,
                    "email_admin": email_admin,
                    "nome_admin": nome_admin,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        tenant = registrar_tenant(
            db=db,
            nome_empresa=nome_empresa,
            slug=slug,
            email_admin=email_admin,
            senha_admin=senha_admin,
            nome_admin=nome_admin,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "tenant/registrar.html",
            {
                "request": request,
                "erro": str(e),
                "form": {
                    "nome_empresa": nome_empresa,
                    "slug": slug,
                    "email_admin": email_admin,
                    "nome_admin": nome_admin,
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return templates.TemplateResponse(
        "tenant/sucesso.html",
        {"request": request, "tenant": tenant},
    )

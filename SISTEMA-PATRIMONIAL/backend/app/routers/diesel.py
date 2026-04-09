"""
Router Diesel — controle de gastos com combustível.

Rotas:
  GET  /admin/diesel       — lista com filtros e KPIs mensais
  GET  /admin/diesel/novo  — formulário de registro
  POST /admin/diesel/novo  — salva registro
  GET  /admin/diesel/{id}/editar  — formulário de edição
  POST /admin/diesel/{id}/editar  — salva edição
  POST /admin/diesel/{id}/excluir — remove registro
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract, func

from app.database import get_db
from app.models.diesel import GastoDiesel
from app.models.filial import Filial
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.routers._shared import brl as _brl, exigir_admin as _exigir_admin

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["brl"] = _brl

_MESES = [
    (1, "Jan"), (2, "Fev"), (3, "Mar"), (4, "Abr"),
    (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Ago"),
    (9, "Set"), (10, "Out"), (11, "Nov"), (12, "Dez"),
]


# ── Lista principal ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def diesel_lista(
    request: Request,
    mes: int = 0,
    ano: int = 0,
    local: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    hoje = date.today()
    if not mes:
        mes = hoje.month
    if not ano:
        ano = hoje.year

    per_page = 40
    q = db.query(GastoDiesel).filter(
        GastoDiesel.tenant_id == tenant.id,
        extract("month", GastoDiesel.data) == mes,
        extract("year",  GastoDiesel.data) == ano,
    )
    if local:
        q = q.filter(GastoDiesel.local.ilike(f"%{local}%"))

    total_count = q.count()
    registros = (
        q.order_by(GastoDiesel.data.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # KPIs do mês
    kpi = db.query(
        func.count(GastoDiesel.id).label("qtd"),
        func.coalesce(func.sum(GastoDiesel.litros), 0).label("litros"),
        func.coalesce(func.sum(GastoDiesel.valor_total), 0).label("total"),
    ).filter(
        GastoDiesel.tenant_id == tenant.id,
        extract("month", GastoDiesel.data) == mes,
        extract("year",  GastoDiesel.data) == ano,
    ).first()

    # Resumo por local no mês
    por_local = db.query(
        GastoDiesel.local,
        func.count(GastoDiesel.id).label("qtd"),
        func.coalesce(func.sum(GastoDiesel.litros), 0).label("litros"),
        func.coalesce(func.sum(GastoDiesel.valor_total), 0).label("total"),
    ).filter(
        GastoDiesel.tenant_id == tenant.id,
        extract("month", GastoDiesel.data) == mes,
        extract("year",  GastoDiesel.data) == ano,
    ).group_by(GastoDiesel.local).order_by(func.sum(GastoDiesel.valor_total).desc()).all()

    # Anos disponíveis
    anos = list(range(2024, hoje.year + 2))
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return templates.TemplateResponse(
        "admin/diesel.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "registros": registros,
            "kpi": kpi,
            "por_local": por_local,
            "mes": mes,
            "ano": ano,
            "local_filtro": local,
            "meses": _MESES,
            "anos": anos,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


# ── Novo registro ─────────────────────────────────────────────────────────────

@router.get("/novo", response_class=HTMLResponse)
def diesel_form_novo(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )
    return templates.TemplateResponse(
        "admin/diesel_form.html",
        {"request": request, "usuario": usuario, "tenant": tenant,
         "registro": None, "erro": None, "filiais": filiais},
    )


@router.post("/novo")
def diesel_criar(
    request: Request,
    data: str = Form(...),
    numero_nota: Optional[str] = Form(None),
    descricao: str = Form(...),
    local: Optional[str] = Form(None),
    tecnico: Optional[str] = Form(None),
    litros: Optional[str] = Form(None),
    valor_litro: Optional[str] = Form(None),
    valor_total: str = Form(...),
    observacoes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    try:
        g = GastoDiesel(
            tenant_id=tenant.id,
            data=datetime.fromisoformat(data),
            numero_nota=int(numero_nota) if numero_nota else None,
            descricao=descricao.strip()[:300],
            local=(local or "").strip()[:150] or None,
            tecnico=(tecnico or "").strip()[:150] or None,
            litros=Decimal(litros.replace(",", ".")) if litros else None,
            valor_litro=Decimal(valor_litro.replace(",", ".")) if valor_litro else None,
            valor_total=Decimal(valor_total.replace(",", ".")),
            observacoes=(observacoes or "").strip() or None,
        )
        db.add(g)
        db.commit()
    except Exception as exc:
        db.rollback()
        filiais = (
            db.query(Filial)
            .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
            .order_by(Filial.nome)
            .all()
        )
        return templates.TemplateResponse(
            "admin/diesel_form.html",
            {
                "request": request, "usuario": usuario, "tenant": tenant,
                "registro": None, "erro": str(exc), "filiais": filiais,
            },
            status_code=422,
        )

    hoje = date.today()
    return RedirectResponse(
        url=f"/admin/diesel/?mes={hoje.month}&ano={hoje.year}&msg=criado",
        status_code=303,
    )


# ── Editar ────────────────────────────────────────────────────────────────────

@router.get("/{registro_id}/editar", response_class=HTMLResponse)
def diesel_form_editar(
    registro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    g = db.query(GastoDiesel).filter(
        GastoDiesel.id == registro_id, GastoDiesel.tenant_id == tenant.id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    filiais = (
        db.query(Filial)
        .filter(Filial.tenant_id == tenant.id, Filial.ativa == True)
        .order_by(Filial.nome)
        .all()
    )
    return templates.TemplateResponse(
        "admin/diesel_form.html",
        {"request": request, "usuario": usuario, "tenant": tenant,
         "registro": g, "erro": None, "filiais": filiais},
    )


@router.post("/{registro_id}/editar")
def diesel_editar(
    registro_id: int,
    data: str = Form(...),
    numero_nota: Optional[str] = Form(None),
    descricao: str = Form(...),
    local: Optional[str] = Form(None),
    tecnico: Optional[str] = Form(None),
    litros: Optional[str] = Form(None),
    valor_litro: Optional[str] = Form(None),
    valor_total: str = Form(...),
    observacoes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    g = db.query(GastoDiesel).filter(
        GastoDiesel.id == registro_id, GastoDiesel.tenant_id == tenant.id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")

    g.data        = datetime.fromisoformat(data)
    g.numero_nota = int(numero_nota) if numero_nota else None
    g.descricao   = descricao.strip()[:300]
    g.local       = (local or "").strip()[:150] or None
    g.tecnico     = (tecnico or "").strip()[:150] or None
    g.litros      = Decimal(litros.replace(",", ".")) if litros else None
    g.valor_litro = Decimal(valor_litro.replace(",", ".")) if valor_litro else None
    g.valor_total = Decimal(valor_total.replace(",", "."))
    g.observacoes = (observacoes or "").strip() or None
    g.updated_at  = datetime.utcnow()
    db.commit()

    dt = g.data
    return RedirectResponse(
        url=f"/admin/diesel/?mes={dt.month}&ano={dt.year}&msg=atualizado",
        status_code=303,
    )


# ── Excluir ────────────────────────────────────────────────────────────────────

@router.post("/{registro_id}/excluir")
def diesel_excluir(
    registro_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_exigir_admin),
    tenant: Tenant = Depends(get_tenant_atual),
):
    g = db.query(GastoDiesel).filter(
        GastoDiesel.id == registro_id, GastoDiesel.tenant_id == tenant.id
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    dt = g.data
    db.delete(g)
    db.commit()
    return RedirectResponse(
        url=f"/admin/diesel/?mes={dt.month}&ano={dt.year}&msg=excluido",
        status_code=303,
    )

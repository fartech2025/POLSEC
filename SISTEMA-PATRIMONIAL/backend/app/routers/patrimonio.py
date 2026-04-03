from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patrimonio import StatusPatrimonio
from app.models.tenant import Tenant
from app.models.usuario import PerfilUsuario
from app.schemas.patrimonio import PatrimonioCreate, PatrimonioUpdate
from app.services.auth_service import get_tenant_atual, get_usuario_logado
from app.services.patrimonio_service import PatrimonioService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _exigir_escrita(usuario=Depends(get_usuario_logado)):
    """Bloqueia visualizador em endpoints de escrita."""
    if usuario.perfil == PerfilUsuario.visualizador:
        raise HTTPException(
            status_code=403,
            detail="Visualizadores não podem criar ou editar patrimônios.",
        )
    return usuario


@router.get("/", response_class=HTMLResponse)
def listar(
    request: Request,
    busca: Optional[str] = None,
    setor: Optional[str] = None,
    status_filtro: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    itens = service.listar(busca=busca, setor=setor, status=status_filtro)
    setores = service.listar_setores()
    return templates.TemplateResponse(
        "patrimonio/lista.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "itens": itens,
            "setores": setores,
            "busca": busca,
            "setor": setor,
            "status_filtro": status_filtro,
            "status_opcoes": StatusPatrimonio,
        },
    )


@router.get("/novo", response_class=HTMLResponse)
def form_novo(
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(_exigir_escrita),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    return templates.TemplateResponse(
        "patrimonio/form.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "item": None,
            "responsaveis": service.listar_responsaveis(),
            "status_opcoes": StatusPatrimonio,
        },
    )


@router.post("/novo")
def criar(
    request: Request,
    codigo: str = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    setor: str = Form(...),
    localizacao: Optional[str] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    valor: Optional[str] = Form(None),
    observacoes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario=Depends(_exigir_escrita),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    dados = PatrimonioCreate(
        codigo=codigo,
        descricao=descricao,
        categoria=categoria,
        setor=setor,
        localizacao=localizacao,
        responsavel_id=responsavel_id,
        valor=float(valor.replace(",", ".")) if valor else None,
        observacoes=observacoes,
    )
    service.criar(dados, usuario_id=usuario.id)
    return RedirectResponse(url="/patrimonio", status_code=302)


@router.get("/{patrimonio_id}", response_class=HTMLResponse)
def detalhe(
    patrimonio_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    item = service.buscar_por_id(patrimonio_id)
    if not item:
        raise HTTPException(status_code=404, detail="Patrimônio não encontrado")
    historico = service.historico(patrimonio_id)
    return templates.TemplateResponse(
        "patrimonio/detalhe.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "item": item,
            "historico": historico,
        },
    )


@router.get("/{patrimonio_id}/editar", response_class=HTMLResponse)
def form_editar(
    patrimonio_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(_exigir_escrita),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    item = service.buscar_por_id(patrimonio_id)
    if not item:
        raise HTTPException(status_code=404, detail="Patrimônio não encontrado")
    return templates.TemplateResponse(
        "patrimonio/form.html",
        {
            "request": request,
            "usuario": usuario,
            "tenant": tenant,
            "item": item,
            "responsaveis": service.listar_responsaveis(),
            "status_opcoes": StatusPatrimonio,
        },
    )


@router.post("/{patrimonio_id}/editar")
def editar(
    patrimonio_id: int,
    descricao: str = Form(...),
    categoria: str = Form(...),
    setor: str = Form(...),
    localizacao: Optional[str] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    valor: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    observacoes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
    tenant: Tenant = Depends(get_tenant_atual),
):
    service = PatrimonioService(db, tenant.id)
    dados = PatrimonioUpdate(
        descricao=descricao,
        categoria=categoria,
        setor=setor,
        localizacao=localizacao,
        responsavel_id=responsavel_id,
        valor=float(valor.replace(",", ".")) if valor else None,
        status=StatusPatrimonio(status) if status else None,
        observacoes=observacoes,
    )
    service.atualizar(patrimonio_id, dados, usuario_id=usuario.id)
    return RedirectResponse(url=f"/patrimonio/{patrimonio_id}", status_code=302)

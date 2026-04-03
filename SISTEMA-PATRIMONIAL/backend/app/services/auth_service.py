"""
Auth Service — Supabase Auth
Toda autenticação é delegada ao Supabase.
O JWT retornado pelo Supabase contém o `sub` (supabase_uid) e claims customizados.
"""
from typing import Optional
from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from supabase import create_client, Client

from app.config import settings
from app.database import get_db
from app.models.usuario import Usuario
from app.models.tenant import Tenant


# ── Supabase client (singleton) ───────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Client com service_role — operações administrativas (criar tenant, listar users)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


# ── Login / Logout ────────────────────────────────────────────────────────────

def login_com_supabase(email: str, senha: str) -> dict:
    """Autentica via Supabase e retorna access_token + refresh_token."""
    sb = get_supabase()
    resposta = sb.auth.sign_in_with_password({"email": email, "password": senha})
    if not resposta.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )
    return {
        "access_token": resposta.session.access_token,
        "refresh_token": resposta.session.refresh_token,
    }


def logout_supabase(access_token: str) -> None:
    sb = get_supabase()
    sb.auth.sign_out()


def registrar_usuario_supabase(email: str, senha: str, metadata: dict = None) -> str:
    """Cria usuário no Supabase Auth e retorna o supabase_uid."""
    sb = get_supabase_admin()
    resposta = sb.auth.admin.create_user({
        "email": email,
        "password": senha,
        "email_confirm": True,
        "user_metadata": metadata or {},
    })
    return resposta.user.id


def solicitar_reset_senha(email: str) -> None:
    sb = get_supabase()
    sb.auth.reset_password_email(email)


# ── Validação de JWT ──────────────────────────────────────────────────────────

def decodificar_token(token: str) -> Optional[dict]:
    """
    Valida o JWT do Supabase com HS256 usando o JWT Secret do projeto.
    O Supabase suporta tanto RS256 (padrão) quanto HS256 (legado).
    Para RS256 configurar SUPABASE_JWT_SECRET com a chave pública.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError:
        return None


# ── Dependency: usuário autenticado ──────────────────────────────────────────

def get_usuario_logado(
    request: Request,
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Extrai e valida o JWT do cookie.
    Retorna o Usuario do banco filtrado pelo tenant corrente.
    Redireciona para /auth/login se inválido.
    """
    _redirecionar = HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": "/auth/login"},
    )

    if not access_token:
        raise _redirecionar

    payload = decodificar_token(access_token)
    if not payload:
        raise _redirecionar

    supabase_uid = payload.get("sub")
    if not supabase_uid:
        raise _redirecionar

    # Tenant corrente (resolvido pelo middleware)
    tenant_slug = getattr(request.state, "tenant_slug", None)

    query = db.query(Usuario).filter(
        Usuario.supabase_uid == supabase_uid,
        Usuario.ativo == True,
    )

    # Filtra pelo tenant se identificado
    if tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if tenant:
            query = query.filter(Usuario.tenant_id == tenant.id)

    usuario = query.first()
    if not usuario:
        raise _redirecionar

    return usuario


def get_tenant_atual(request: Request, db: Session = Depends(get_db)) -> Tenant:
    """Retorna o Tenant corrente com base no slug resolvido pelo middleware."""
    slug = getattr(request.state, "tenant_slug", None)
    if not slug:
        raise HTTPException(status_code=400, detail="Tenant não identificado.")
    tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.ativo == True).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Empresa '{slug}' não encontrada.")
    return tenant


def requer_perfil(*perfis):
    """Decorator de dependência para restringir acesso por perfil."""
    from app.models.usuario import PerfilUsuario

    def verificar(usuario: Usuario = Depends(get_usuario_logado)):
        if usuario.perfil not in perfis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação.",
            )
        return usuario

    return verificar

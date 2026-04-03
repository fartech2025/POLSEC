"""
Tenant Service — Onboarding e gestão de tenants.
Registra nova empresa: cria Supabase Auth user + Tenant + Usuario admin.
"""
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.tenant import Tenant
from app.models.usuario import Usuario, PerfilUsuario
from app.services.auth_service import registrar_usuario_supabase


def registrar_tenant(
    db: Session,
    nome_empresa: str,
    slug: str,
    email_admin: str,
    senha_admin: str,
    nome_admin: str,
    plano: str = "basico",
) -> Tenant:
    """
    Cria um novo tenant (empresa) e seu usuário administrador.
    Passos:
      1. Valida que o slug está disponível
      2. Cria o usuário no Supabase Auth
      3. Cria o registro Tenant no banco
      4. Cria o registro Usuario admin vinculado ao tenant
    """
    # 1. Slug único
    existente = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O identificador '{slug}' já está em uso.",
        )

    # 2. Cria usuário no Supabase Auth
    supabase_uid = registrar_usuario_supabase(
        email=email_admin,
        senha=senha_admin,
        metadata={"nome": nome_admin, "empresa": nome_empresa, "slug": slug},
    )

    # 3. Cria o Tenant
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        slug=slug,
        nome=nome_empresa,
        email_admin=email_admin,
        plano=plano,
        ativo=True,
    )
    db.add(tenant)
    db.flush()

    # 4. Cria o Usuario admin
    usuario = Usuario(
        supabase_uid=supabase_uid,
        tenant_id=tenant_id,
        nome=nome_admin,
        email=email_admin,
        perfil=PerfilUsuario.administrador,
        ativo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(tenant)
    return tenant


def buscar_tenant_por_slug(db: Session, slug: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.slug == slug, Tenant.ativo == True).first()


def listar_tenants(db: Session) -> list[Tenant]:
    return db.query(Tenant).order_by(Tenant.nome).all()

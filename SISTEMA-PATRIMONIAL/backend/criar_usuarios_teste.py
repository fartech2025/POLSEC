"""
Script único: cria usuários de teste POLSEC para cada perfil do sistema.
Execute uma vez: python criar_usuarios_teste.py
"""
import sys
import os

# Garante que o módulo app está no path
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app.database import SessionLocal
from app.models.usuario import Usuario, PerfilUsuario
from app.models.tenant import Tenant
from app.services.auth_service import get_supabase_admin, registrar_usuario_supabase

# ── Usuários a criar ──────────────────────────────────────────────────────────
USUARIOS_POLSEC = [
    {
        "nome": "Admin POLSEC",
        "email": "admin@polsec.app.br",        # já existe — apenas confirma
        "senha": "Polsec@2026",
        "perfil": PerfilUsuario.administrador,
        "ja_existe": True,
    },
    {
        "nome": "Técnico POLSEC",
        "email": "tecnico@polsec.app.br",
        "senha": "Tecnico@2026",
        "perfil": PerfilUsuario.operador,
        "ja_existe": False,
    },
    {
        "nome": "Visualizador POLSEC",
        "email": "viewer@polsec.app.br",
        "senha": "Viewer@2026",
        "perfil": PerfilUsuario.visualizador,
        "ja_existe": False,
    },
]


def main():
    db = SessionLocal()
    try:
        # Busca o tenant POLSEC
        tenant = db.query(Tenant).filter(Tenant.slug == "polsec").first()
        if not tenant:
            print("❌ Tenant POLSEC não encontrado. Verifique o banco.")
            return

        print(f"✅ Tenant encontrado: {tenant.nome} (id={tenant.id})\n")
        print(f"{'PERFIL':<20} {'E-MAIL':<35} {'SENHA':<20} {'STATUS'}")
        print("-" * 90)

        for u in USUARIOS_POLSEC:
            email = u["email"]

            # Verifica se já existe no banco local
            existente_db = db.query(Usuario).filter(
                Usuario.email == email,
                Usuario.tenant_id == tenant.id,
            ).first()

            if u["ja_existe"] or existente_db:
                print(f"{u['perfil'].value:<20} {email:<35} {u['senha']:<20} já existia ✓")
                continue

            # Cria no Supabase Auth
            try:
                supabase_uid = registrar_usuario_supabase(
                    email=email,
                    senha=u["senha"],
                    metadata={"nome": u["nome"], "empresa": tenant.nome, "slug": tenant.slug},
                )
            except Exception as e:
                # Pode já existir no Supabase mas não no banco local
                # Tenta buscar pelo email no Supabase Admin
                try:
                    sb = get_supabase_admin()
                    users_list = sb.auth.admin.list_users()
                    existing = next(
                        (x for x in users_list if x.email == email), None
                    )
                    if existing:
                        supabase_uid = existing.id
                    else:
                        print(f"{u['perfil'].value:<20} {email:<35} {'':20} ❌ Erro Supabase: {e}")
                        continue
                except Exception:
                    print(f"{u['perfil'].value:<20} {email:<35} {'':20} ❌ {e}")
                    continue

            # Cria no banco local
            usuario = Usuario(
                supabase_uid=supabase_uid,
                tenant_id=tenant.id,
                nome=u["nome"],
                email=email,
                perfil=u["perfil"],
                ativo=True,
            )
            db.add(usuario)
            db.commit()
            print(f"{u['perfil'].value:<20} {email:<35} {u['senha']:<20} criado ✅")

        print("\nPronto! Faça login em http://localhost:8000 com qualquer usuário acima.")
        print("Dica: use o campo 'tenant' = 'polsec' (cookie tenant_slug).")

    finally:
        db.close()


if __name__ == "__main__":
    main()

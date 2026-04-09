"""
Utilitários compartilhados entre routers administrativos.
"""
from fastapi import Depends, HTTPException, status

from app.models.usuario import PerfilUsuario, Usuario
from app.services.auth_service import get_usuario_logado


def brl(value) -> str:
    """Formata valor no padrão monetário brasileiro: 1.234,56"""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def exigir_admin(usuario: Usuario = Depends(get_usuario_logado)) -> Usuario:
    if usuario.perfil not in (PerfilUsuario.administrador, PerfilUsuario.superadmin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario

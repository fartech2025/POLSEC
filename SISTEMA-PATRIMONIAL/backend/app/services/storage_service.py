"""
Storage Service — compressão de imagens com Pillow e upload para Supabase Storage.

Bucket: polsec-anexos
Estrutura de pastas dentro do bucket:
    {tenant_slug}/chamados/{chamado_id}/fotos/
    {tenant_slug}/chamados/{chamado_id}/orcamentos/
    {tenant_slug}/chamados/{chamado_id}/notas_fiscais/
    {tenant_slug}/chamados/{chamado_id}/laudos/

Compressão de fotos:
    - Redimensiona para máximo 1920px (maior dimensão), mantendo proporção
    - Converte para WebP com qualidade 75
    - Redução média de ~85% no tamanho
"""
import io
import logging
import mimetypes
import os
import re
import uuid
from typing import BinaryIO

from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

_BUCKET = "polsec-anexos"
_MAX_PIXELS = 1920
_WEBP_QUALITY = 75


def _get_storage():
    """Retorna o cliente de storage do Supabase (importação tardia para evitar ciclo)."""
    from app.services.auth_service import get_supabase_admin  # noqa: PLC0415
    return get_supabase_admin().storage


# ── Compressão ────────────────────────────────────────────────────────────────

def comprimir_imagem(dados: bytes) -> tuple[bytes, str]:
    """
    Recebe bytes de uma imagem, retorna (bytes_comprimidos, mime_type).
    Converte para WebP, max 1920px, quality 75.
    """
    img = Image.open(io.BytesIO(dados))
    try:
        # Converte para RGB para garantir compatibilidade WebP
        if img.mode not in ("RGB", "RGBA"):
            converted = img.convert("RGB")
            img.close()
            img = converted
        # Redimensiona mantendo proporção
        img.thumbnail((_MAX_PIXELS, _MAX_PIXELS), Image.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=_WEBP_QUALITY, optimize=True)
        return output.getvalue(), "image/webp"
    finally:
        img.close()


# ── Upload ────────────────────────────────────────────────────────────────────

def fazer_upload(
    bucket_path: str,
    dados: bytes,
    mime_type: str,
) -> str:
    """
    Faz upload dos bytes para o bucket Supabase Storage.
    Retorna o bucket_path confirmado.
    Levanta RuntimeError em caso de falha.
    """
    storage = _get_storage()
    result = storage.from_(_BUCKET).upload(
        path=bucket_path,
        file=dados,
        file_options={"content-type": mime_type, "upsert": "true"},
    )
    # O SDK Supabase Python levanta exceção em erro; se chegou aqui, upload ok.
    logger.info("Upload concluído: %s (%d KB)", bucket_path, len(dados) // 1024)
    return bucket_path


def gerar_url_publica(bucket_path: str) -> str:
    """Retorna a URL pública do arquivo (bucket deve ser público)."""
    storage = _get_storage()
    response = storage.from_(_BUCKET).get_public_url(bucket_path)
    return response


def gerar_url_assinada(bucket_path: str, expira_em: int = 3600) -> str:
    """Retorna URL assinada válida por `expira_em` segundos (para buckets privados)."""
    storage = _get_storage()
    response = storage.from_(_BUCKET).create_signed_url(bucket_path, expira_em)
    return response.get("signedURL", "")


def remover_arquivo(bucket_path: str) -> None:
    """Remove o arquivo do bucket."""
    storage = _get_storage()
    storage.from_(_BUCKET).remove([bucket_path])
    logger.info("Arquivo removido do bucket: %s", bucket_path)


# ── Helpers de caminho ────────────────────────────────────────────────────────

_FILENAME_SAFE = re.compile(r"[^\w.\-]")


def sanitizar_filename(nome: str) -> str:
    """
    Remove path traversal e caracteres inseguros do nome de arquivo.
    Substitui qualquer char não-alfanumérico (exceto ponto e hífen) por '_'.
    Qualquer '/' ou '\' é interpretado pelo bucket como subpasta — removemos.
    OWASP A03: previne path traversal no storage.
    """
    # Remove componentes de diretório (ex: ../../secret.pdf → secret.pdf)
    nome = os.path.basename(nome.replace("\\", "/"))
    # Substitui chars perigosos por underscore
    nome = _FILENAME_SAFE.sub("_", nome)
    # Garante que não fique vazio
    if not nome or nome in (".", ".."):
        nome = "arquivo"
    return nome


def montar_path_foto(tenant_slug: str, chamado_id: int, filename: str) -> str:
    return f"{tenant_slug}/chamados/{chamado_id}/fotos/{sanitizar_filename(filename)}"


def montar_path_orcamento(tenant_slug: str, chamado_id: int, filename: str) -> str:
    return f"{tenant_slug}/chamados/{chamado_id}/orcamentos/{sanitizar_filename(filename)}"


def montar_path_nota_fiscal(tenant_slug: str, chamado_id: int, filename: str) -> str:
    return f"{tenant_slug}/chamados/{chamado_id}/notas_fiscais/{sanitizar_filename(filename)}"


def montar_path_laudo(tenant_slug: str, chamado_id: int, filename: str) -> str:
    return f"{tenant_slug}/chamados/{chamado_id}/laudos/{sanitizar_filename(filename)}"


def montar_path_outro(tenant_slug: str, chamado_id: int, filename: str) -> str:
    return f"{tenant_slug}/chamados/{chamado_id}/outros/{sanitizar_filename(filename)}"


# ── Função principal de processamento ────────────────────────────────────────

def processar_e_enviar_foto(
    dados_originais: bytes,
    tenant_slug: str,
    chamado_id: int,
    nome_base: str,
) -> tuple[str, str, int]:
    """
    Recebe bytes brutos de uma foto, comprime, faz upload.
    Retorna (bucket_path, mime_type, tamanho_kb).
    """
    dados_comprimidos, mime_type = comprimir_imagem(dados_originais)
    filename = f"{nome_base}.webp"
    path = montar_path_foto(tenant_slug, chamado_id, filename)
    fazer_upload(path, dados_comprimidos, mime_type)
    tamanho_kb = len(dados_comprimidos) // 1024
    return path, mime_type, tamanho_kb


def processar_e_enviar_documento(
    dados: bytes,
    bucket_path: str,
) -> tuple[str, str, int]:
    """
    Upload direto de documentos (PDF, XML) sem compressão.
    Retorna (bucket_path, mime_type, tamanho_kb).
    """
    mime_type, _ = mimetypes.guess_type(bucket_path)
    mime_type = mime_type or "application/octet-stream"
    fazer_upload(bucket_path, dados, mime_type)
    tamanho_kb = len(dados) // 1024
    return bucket_path, mime_type, tamanho_kb

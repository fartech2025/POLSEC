"""
importar_patrimonio.py
Lê o arquivo "FOR IE02 - CONTROLE PATRIMONIAL - V1.numbers" e importa os registros
para a tabela `patrimonios` do banco de dados.

Uso:
    python importar_patrimonio.py [--tenant-id UUID] [--arquivo CAMINHO] [--dry-run]

Comportamento:
  - Campos não preenchidos na planilha recebem valor zero/vazio/None.
  - Registros com código já existente no tenant são IGNORADOS (sem sobrescrever).
  - Exibe progresso e resumo no final.

Dependências extras:
    pip install numbers-parser
"""
import argparse
import os
import sys

# Garante que app/ seja encontrado quando rodado de dentro de backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal, InvalidOperation

import numbers_parser

from app.database import SessionLocal
from app.models.patrimonio import Patrimonio, StatusPatrimonio

# ── Configurações padrão ──────────────────────────────────────────────────────
DEFAULT_TENANT_ID = "dd3ce17e-b506-46cf-9cce-707b20d1e253"   # POLSEC
DEFAULT_ARQUIVO   = "/Volumes/FDIAS 320 GB/FOR IE02 - CONTROLE PATRIMONIAL - V1.numbers"

# ── Mapeamento de colunas da planilha ─────────────────────────────────────────
# Índices confirmados na inspeção do arquivo:
#   0: PAT.            → código base
#   1: EQUIPAMENTO     → descrição
#   2: ID/N° DE SÉRIE  → série (vai para observações)
#   3: UNIDADE         → setor
#   4: LOCAL           → localização
#   5: NOTA FISCAL     → observações (complemento)
#   6: VALOR UNITÁRIO  → valor fallback
#   7: OBSERVAÇÕES     → observações
#   8: VALOR           → valor principal
COL_PAT        = 0
COL_EQUIP      = 1
COL_SERIE      = 2
COL_UNIDADE    = 3
COL_LOCAL      = 4
COL_NF         = 5
COL_VUNIT      = 6
COL_OBS        = 7
COL_VALOR      = 8

# ── Palavras-chave para auto-categorização ────────────────────────────────────
_CATEGORIAS = [
    (["notebook", "computador", "desktop", "monitor", "teclado", "mouse", "impressora",
      "scanner", "servidor", "switch", "roteador", "access point", "ap ", "wifi", "onu",
      "olt", "rack", "splitter", "conversor", "transceiver", "sfp", "ups", "nobreak"],
     "TI / Telecomunicações"),
    (["celular", "smartphone", "tablet", "radio", "rádio"],
     "Telecom / Mobile"),
    (["antena", "torre", "cabo", "fibra", "conector"],
     "Infraestrutura de Rede"),
    (["veículo", "carro", "moto", "caminhão", "caminhonete"],
     "Frota / Veículos"),
    (["ar condicionado", "ar-condicionado", "climatizador"],
     "Climatização"),
    (["câmera", "camera", "dvr", "nvr", "cftv"],
     "Segurança / CFTV"),
    (["mesa", "cadeira", "armário", "estante", "mobiliário", "móvel"],
     "Mobiliário"),
    (["gerador", "grupo gerador", "baterias", "bateria"],
     "Energia"),
]
_CATEGORIA_PADRAO = "Não categorizado"


def _categorizar(descricao: str) -> str:
    desc = (descricao or "").lower()
    for palavras, categoria in _CATEGORIAS:
        for p in palavras:
            if p in desc:
                return categoria
    return _CATEGORIA_PADRAO


def _str_val(cell_value) -> str:
    """Converte valor de célula para string, retornando '' se None."""
    if cell_value is None:
        return ""
    if isinstance(cell_value, float) and cell_value == int(cell_value):
        return str(int(cell_value))
    return str(cell_value).strip()


def _decimal_val(cell_value) -> Decimal:
    """Converte valor de célula para Decimal; retorna Decimal('0') se inválido."""
    if cell_value is None:
        return Decimal("0")
    try:
        return Decimal(str(cell_value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def _gerar_codigo(pat_raw, row_idx: int) -> str:
    """Gera um código único a partir do campo PAT. da planilha."""
    if pat_raw is None:
        return f"IMP-{row_idx:05d}"
    val = _str_val(pat_raw).strip()
    if not val:
        return f"IMP-{row_idx:05d}"
    # Numeric → PAT-00001
    try:
        num = int(float(val))
        return f"PAT-{num:05d}"
    except (ValueError, TypeError):
        pass
    # Texto (ex.: "SPAT") → SPAT-00001
    val_clean = val.upper().replace(" ", "-")
    return f"{val_clean}-{row_idx:05d}"


def importar(tenant_id: str, arquivo: str, dry_run: bool = False):
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Importando: {os.path.basename(arquivo)}")
    print(f"Tenant ID : {tenant_id}")
    print("-" * 60)

    doc   = numbers_parser.Document(arquivo)
    table = doc.sheets[0].tables[0]   # Sheet "PATRIMÔNIO", Tabela 1
    total_planilha = table.num_rows - 1  # desconta cabeçalho

    db = SessionLocal()

    # Códigos já existentes no tenant (para skip/dedup rápido)
    existentes = {
        cod for (cod,) in db.query(Patrimonio.codigo)
                             .filter(Patrimonio.tenant_id == tenant_id)
                             .all()
    }

    inseridos = 0
    ignorados_vazio = 0
    ignorados_duplicado = 0
    erros = 0

    try:
        for row in range(1, table.num_rows):
            pat_raw  = table.cell(row, COL_PAT).value
            equip    = _str_val(table.cell(row, COL_EQUIP).value)

            # Linha vazia — pula
            if pat_raw is None and not equip:
                ignorados_vazio += 1
                continue

            codigo = _gerar_codigo(pat_raw, row)

            # Duplicata — pula sem sobrescrever
            if codigo in existentes:
                ignorados_duplicado += 1
                continue

            # ── Campos da planilha ────────────────────────────────────────
            serie     = _str_val(table.cell(row, COL_SERIE).value)
            unidade   = _str_val(table.cell(row, COL_UNIDADE).value) or "Não informado"
            local_    = _str_val(table.cell(row, COL_LOCAL).value)
            nf        = _str_val(table.cell(row, COL_NF).value)
            obs_orig  = _str_val(table.cell(row, COL_OBS).value)
            vunit     = _decimal_val(table.cell(row, COL_VUNIT).value)
            valor     = _decimal_val(table.cell(row, COL_VALOR).value)

            # Valor: usa col VALOR; se zero, tenta VALOR UNITÁRIO
            valor_final = valor if valor > 0 else vunit

            # Monta observações completas
            partes_obs = []
            if serie:
                partes_obs.append(f"N° Série: {serie}")
            if nf:
                partes_obs.append(f"NF: {nf}")
            if obs_orig:
                partes_obs.append(obs_orig)
            observacoes = " | ".join(partes_obs) if partes_obs else None

            descricao  = equip or "Não informado"
            categoria  = _categorizar(descricao)
            setor      = unidade
            localizacao = local_ or None

            try:
                novo = Patrimonio(
                    tenant_id    = tenant_id,
                    codigo       = codigo,
                    descricao    = descricao[:255],
                    categoria    = categoria,
                    setor        = setor[:100],
                    localizacao  = localizacao[:150] if localizacao else None,
                    valor        = valor_final if valor_final > 0 else None,
                    status       = StatusPatrimonio.ativo,
                    observacoes  = observacoes,
                    data_aquisicao = None,   # não disponível na planilha
                )
                if not dry_run:
                    db.add(novo)
                existentes.add(codigo)
                inseridos += 1

                # Commit em lotes para evitar transação gigante
                if not dry_run and inseridos % 500 == 0:
                    db.commit()
                    print(f"  → {inseridos} registros inseridos até agora...")

            except Exception as exc:
                erros += 1
                print(f"  [ERRO] Linha {row} (código {codigo}): {exc}")
                db.rollback()

        if not dry_run and inseridos % 500 != 0:
            db.commit()

    finally:
        db.close()

    # ── Relatório final ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"Linhas na planilha  : {total_planilha}")
    print(f"Inseridos           : {inseridos}")
    print(f"Ignorados (vazios)  : {ignorados_vazio}")
    print(f"Ignorados (duplic.) : {ignorados_duplicado}")
    print(f"Erros               : {erros}")
    print("=" * 60)
    if dry_run:
        print("[DRY-RUN] Nenhuma alteração foi salva no banco.")
    else:
        print("Importação concluída.")


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa planilha FOR IE02 para o banco de dados patrimonial."
    )
    parser.add_argument(
        "--tenant-id",
        default=DEFAULT_TENANT_ID,
        help=f"UUID do tenant de destino (padrão: POLSEC {DEFAULT_TENANT_ID})",
    )
    parser.add_argument(
        "--arquivo",
        default=DEFAULT_ARQUIVO,
        help="Caminho para o arquivo .numbers",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a importação sem gravar no banco",
    )
    args = parser.parse_args()
    importar(args.tenant_id, args.arquivo, args.dry_run)

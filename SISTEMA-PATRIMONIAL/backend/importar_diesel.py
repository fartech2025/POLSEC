"""
importar_diesel.py — importa registros de abastecimento de diesel do Excel.

Uso:
    .venv/bin/python3 importar_diesel.py "XXX - Controle de chamados abertos - Proj. São Paulo (1).xlsx" --tenant polsec
"""
import argparse
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
from app.database import SessionLocal
from app.models.diesel import GastoDiesel
from app.models.tenant import Tenant


def _extract_local(descricao: str) -> str | None:
    """Extrai o local do abastecimento da descrição. Ex: 'Abastecimento Óleo diesel - Limeira' → 'Limeira'"""
    if not descricao:
        return None
    parts = descricao.rsplit(" - ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("arquivo")
    p.add_argument("--tenant", default="polsec")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main():
    args = _parse_args()
    arquivo = Path(args.arquivo)
    if not arquivo.exists():
        print(f"[ERRO] Arquivo não encontrado: {arquivo}")
        sys.exit(1)

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.nome.ilike(f"%{args.tenant}%")).first()
        if not tenant:
            print(f"[ERRO] Tenant '{args.tenant}' não encontrado.")
            sys.exit(1)
        print(f"[OK] Tenant: {tenant.nome}")

        wb = openpyxl.load_workbook(arquivo, data_only=True)
        ws = wb["Gasto diesel 2026"]

        inseridos = 0
        pulados = 0
        erros = 0

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            data = row[0]
            if not isinstance(data, datetime):
                continue

            numero_nota = row[1]
            descricao   = str(row[2] or "").strip()
            tecnico     = str(row[3] or "").strip() or None
            litros_raw  = row[4]
            vlitro_raw  = row[5]
            vtotal_raw  = row[6]

            if not descricao or vtotal_raw is None:
                continue

            # Idempotência por numero_nota
            if numero_nota:
                existe = db.query(GastoDiesel).filter(
                    GastoDiesel.tenant_id == tenant.id,
                    GastoDiesel.numero_nota == int(numero_nota),
                ).first()
                if existe:
                    pulados += 1
                    continue

            try:
                local = _extract_local(descricao)
                g = GastoDiesel(
                    tenant_id=tenant.id,
                    data=data,
                    numero_nota=int(numero_nota) if numero_nota else None,
                    descricao=descricao[:300],
                    local=local[:150] if local else None,
                    tecnico=tecnico[:150] if tecnico else None,
                    litros=Decimal(str(round(float(litros_raw), 3))) if litros_raw else None,
                    valor_litro=Decimal(str(round(float(vlitro_raw), 3))) if vlitro_raw else None,
                    valor_total=Decimal(str(round(float(vtotal_raw), 2))),
                )
                db.add(g)
                inseridos += 1
            except Exception as exc:
                print(f"[ERRO] Linha {row_idx}: {exc}")
                erros += 1

        if not args.dry_run:
            db.commit()
            print("[OK] Commit realizado.")
        else:
            db.rollback()
            print("[DRY-RUN] Nenhuma alteração gravada.")

        print(f"\nResumo:")
        print(f"  Inseridos : {inseridos}")
        print(f"  Pulados   : {pulados}")
        print(f"  Erros     : {erros}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""
importar_chamados.py — importa chamados históricos da planilha Excel para o banco.

Uso:
    .venv/bin/python3 importar_chamados.py "XXX - Controle de chamados abertos - Proj. São Paulo (1).xlsx" --tenant polsec

O script:
  - Lê a aba "Controle de Chamados abertos" (linha 1 = cabeçalho, dados a partir da linha 3)
  - Resolve a filial pelo nome (código numérico antes do hífen)
  - Cria o chamado com status baseado na presença de data_conclusao
  - Ignora linhas sem Número de Chamado
  - Idempotente: pula chamados cujo numero_chamado já existe no tenant
"""
import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
from sqlalchemy import text
from sqlalchemy.orm import Session

# ── config path ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from app.database import SessionLocal
from app.models.chamado import Chamado, StatusChamado, TipoChamado, PrioridadeChamado
from app.models.filial import Filial
from app.models.tenant import Tenant
from app.models.glosa import GlosaChamado, StatusGlosa


def _parse_args():
    p = argparse.ArgumentParser(description="Importa chamados históricos do Excel")
    p.add_argument("arquivo", help="Caminho do .xlsx")
    p.add_argument("--tenant", default="polsec",
                   help="Slug ou início do nome do tenant (default: polsec)")
    p.add_argument("--dry-run", action="store_true",
                   help="Simula sem gravar no banco")
    return p.parse_args()


def _td_to_horas(td) -> float | None:
    """Converte timedelta (vindo do openpyxl) em horas float."""
    if td is None:
        return None
    if isinstance(td, timedelta):
        return td.total_seconds() / 3600
    return None


def _extract_codigo(nome_unidade: str) -> str:
    """Extrai o código da unidade do texto 'X.YZ - Nome da unidade'."""
    if not nome_unidade:
        return ""
    return nome_unidade.split(" - ")[0].strip()


def main():
    args = _parse_args()
    arquivo = Path(args.arquivo)
    if not arquivo.exists():
        print(f"[ERRO] Arquivo não encontrado: {arquivo}")
        sys.exit(1)

    db: Session = SessionLocal()
    try:
        # ── Resolve tenant ───────────────────────────────────────────────────
        tenant = (
            db.query(Tenant)
            .filter(Tenant.nome.ilike(f"%{args.tenant}%"))
            .first()
        )
        if not tenant:
            print(f"[ERRO] Tenant '{args.tenant}' não encontrado.")
            sys.exit(1)
        print(f"[OK] Tenant: {tenant.nome} ({tenant.id})")

        # ── Cria/busca patrimônio genérico via SQL direto ────────────────────
        pat_row = db.execute(
            text("SELECT id FROM patrimonios WHERE tenant_id = :tid AND codigo = 'IMP-HISTORICO' LIMIT 1"),
            {"tid": tenant.id},
        ).fetchone()
        if pat_row:
            pat_id = pat_row[0]
            print(f"[OK] Patrimônio IMP-HISTORICO já existe (id={pat_id}).")
        else:
            db.execute(
                text("""
                    INSERT INTO patrimonios (tenant_id, codigo, descricao, categoria, setor, created_at, updated_at)
                    VALUES (:tid, 'IMP-HISTORICO', 'Patrimônio de Importação Histórica (planilha)', 'Outros', 'Importação', now(), now())
                """),
                {"tid": tenant.id},
            )
            db.commit()
            pat_id = db.execute(
                text("SELECT id FROM patrimonios WHERE tenant_id = :tid AND codigo = 'IMP-HISTORICO' LIMIT 1"),
                {"tid": tenant.id},
            ).fetchone()[0]
            print(f"[OK] Patrimônio IMP-HISTORICO criado (id={pat_id}).")

        # ── Cria/busca funcionário genérico via SQL direto ───────────────────
        func_row = db.execute(
            text("SELECT id FROM funcionarios WHERE tenant_id = :tid AND email = 'importacao@sistema' LIMIT 1"),
            {"tid": tenant.id},
        ).fetchone()
        if func_row:
            func_id = func_row[0]
            print(f"[OK] Funcionário de importação já existe (id={func_id}).")
        else:
            # Busca cargo existente do tenant
            cargo_row = db.execute(
                text("SELECT id FROM cargos WHERE tenant_id = :tid LIMIT 1"),
                {"tid": tenant.id},
            ).fetchone()
            if not cargo_row:
                db.execute(
                    text("""
                        INSERT INTO cargos (tenant_id, nome, nivel_hierarquico, permissoes, ativo, created_at, updated_at)
                        VALUES (:tid, 'Importação Histórica', 99, '{}', true, now(), now())
                    """),
                    {"tid": tenant.id},
                )
                db.commit()
                cargo_row = db.execute(
                    text("SELECT id FROM cargos WHERE tenant_id = :tid LIMIT 1"),
                    {"tid": tenant.id},
                ).fetchone()
                print(f"[OK] Cargo de importação criado (id={cargo_row[0]}).")
            cargo_id = cargo_row[0]
            db.execute(
                text("""
                    INSERT INTO funcionarios (tenant_id, matricula, nome, email, cargo_id, ativo, created_at, updated_at)
                    VALUES (:tid, 'IMP-0000', 'Sistema (importação histórica)', 'importacao@sistema', :cargo_id, false, now(), now())
                """),
                {"tid": tenant.id, "cargo_id": cargo_id},
            )
            db.commit()
            func_id = db.execute(
                text("SELECT id FROM funcionarios WHERE tenant_id = :tid AND email = 'importacao@sistema' LIMIT 1"),
                {"tid": tenant.id},
            ).fetchone()[0]
            print(f"[OK] Funcionário de importação criado (id={func_id}).")

        # ── Mapa de filiais por código (ex: "3.07", "1.01") ─────────────────
        filiais_db = db.query(Filial).filter(Filial.tenant_id == tenant.id).all()
        # filial.nome pode ter formato "3.07 - Nome" ou só "Nome"
        filial_por_codigo: dict[str, Filial] = {}
        for f in filiais_db:
            cod = _extract_codigo(f.nome)
            if cod:
                filial_por_codigo[cod] = f
            # também indexa pelo nome completo normalizado
            filial_por_codigo[f.nome.strip().lower()] = f

        # ── Lê Excel ─────────────────────────────────────────────────────────
        wb = openpyxl.load_workbook(arquivo, data_only=True)
        ws = wb["Controle de Chamados abertos"]

        inseridos = 0
        pulados = 0
        erros = 0

        for row_idx, row in enumerate(
            ws.iter_rows(min_row=3, values_only=True), start=3
        ):
            # col 1 = Número do Chamado
            num = row[0]
            if num is None or not isinstance(num, (int, float)):
                continue

            num = int(num)
            nome_unidade  = str(row[1] or "").strip()
            tipo_raw      = str(row[2] or "").strip().lower()
            glosa_sim     = str(row[3] or "").strip().lower() == "sim"
            dt_abertura   = row[4]
            dt_chegada    = row[5]
            justificativa = str(row[7] or "").strip() or None
            dt_conclusao  = row[8]
            dt_glosa_ini  = row[10]
            td_glosa      = row[11]
            resumo        = str(row[12] or "").strip() or f"Chamado #{num}"
            empresa       = str(row[37] if len(row) > 37 else "").strip() or None

            # Normaliza tipo
            if "corretiva" in tipo_raw:
                tipo = TipoChamado.corretiva
            elif "preventiva" in tipo_raw:
                tipo = TipoChamado.preventiva
            else:
                tipo = None

            # Idempotência: pula se já existe
            existe = (
                db.query(Chamado)
                .filter(
                    Chamado.tenant_id == tenant.id,
                    Chamado.numero_chamado == num,
                )
                .first()
            )
            if existe:
                pulados += 1
                continue

            # Resolve filial
            codigo_unidade = _extract_codigo(nome_unidade)
            filial = filial_por_codigo.get(codigo_unidade)
            if not filial and nome_unidade:
                filial = filial_por_codigo.get(nome_unidade.lower())

            # Status baseado em data_conclusao
            if dt_conclusao and isinstance(dt_conclusao, datetime):
                status = StatusChamado.concluido
            else:
                status = StatusChamado.aberto

            try:
                chamado = Chamado(
                    tenant_id=tenant.id,
                    patrimonio_id=pat_id,
                    solicitante_id=func_id,
                    filial_id=filial.id if filial else None,
                    titulo=resumo[:200],
                    descricao=resumo,
                    status=status,
                    prioridade=PrioridadeChamado.media,
                    numero_chamado=num,
                    tipo_chamado=tipo,
                    codigo_unidade=codigo_unidade or None,
                    data_abertura=dt_abertura if isinstance(dt_abertura, datetime) else datetime.utcnow(),
                    data_chegada_tecnico=dt_chegada if isinstance(dt_chegada, datetime) else None,
                    justificativa_atraso=justificativa,
                    data_conclusao=dt_conclusao if isinstance(dt_conclusao, datetime) else None,
                )
                db.add(chamado)
                db.flush()  # obtém chamado.id

                # Cria GlosaChamado se glosa = Sim e temos data de início
                if glosa_sim and isinstance(dt_glosa_ini, datetime):
                    horas_glosa = _td_to_horas(td_glosa)
                    dt_fim_glosa = None
                    if horas_glosa and isinstance(dt_glosa_ini, datetime):
                        dt_fim_glosa = dt_glosa_ini + timedelta(hours=horas_glosa)

                    glosa = GlosaChamado(
                        tenant_id=tenant.id,
                        chamado_id=chamado.id,
                        filial_id=filial.id if filial else None,
                        filial_nome=nome_unidade[:150] if nome_unidade else "—",
                        data_inicio=dt_glosa_ini,
                        data_fim=dt_fim_glosa,
                        horas_indisponiveis=Decimal(str(round(horas_glosa, 2))) if horas_glosa else None,
                        motivo=resumo[:500],
                        registrado_por_id=func_id,
                        status=StatusGlosa.encerrada if dt_fim_glosa else StatusGlosa.ativa,
                    )
                    db.add(glosa)

                inseridos += 1
                if inseridos % 50 == 0:
                    print(f"  ... {inseridos} inseridos até agora ...")

            except Exception as exc:
                print(f"[ERRO] Linha {row_idx} (chamado #{num}): {exc}")
                db.rollback()
                erros += 1
                continue

        if not args.dry_run:
            db.commit()
            print(f"\n[OK] Commit realizado.")
        else:
            db.rollback()
            print(f"\n[DRY-RUN] Nenhuma alteração gravada.")

        print(f"\nResumo:")
        print(f"  Inseridos : {inseridos}")
        print(f"  Pulados   : {pulados} (já existiam)")
        print(f"  Erros     : {erros}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

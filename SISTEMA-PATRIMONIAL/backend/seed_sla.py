"""
Script de migração — cria a tabela sla_configs e semeia os prazos padrão para o tenant POLSEC.
Execute uma única vez: python seed_sla.py
"""
import os
import sys

# Garante que o módulo app seja encontrado quando rodado a partir de backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine, SessionLocal
from app.models import sla  # noqa: F401 — garante que SLAConfig seja registrado no metadata
from app.services.sla_service import seed_sla_padrao

POLSEC_TENANT_ID = "dd3ce17e-b506-46cf-9cce-707b20d1e253"

# Cria a tabela se ainda não existir
Base.metadata.create_all(bind=engine, tables=[sla.SLAConfig.__table__])
print("✓ Tabela sla_configs pronta.")

# Semeia prazos padrão para POLSEC
db = SessionLocal()
try:
    seed_sla_padrao(POLSEC_TENANT_ID, db)
    print("✓ SLAs padrão criados para POLSEC.")
finally:
    db.close()

print("Concluído.")

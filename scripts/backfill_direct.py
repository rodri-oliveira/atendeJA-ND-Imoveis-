#!/usr/bin/env python3
"""Backfill direto via sqlite3 (sem SQLAlchemy) para evitar locks."""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "dev.db"

conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
cursor = conn.cursor()

# Buscar properties sem ref_code
cursor.execute("""
    SELECT id, external_id 
    FROM re_properties 
    WHERE ref_code IS NULL OR ref_code = ''
""")
rows = cursor.fetchall()

print(f"Encontrados {len(rows)} registros sem ref_code")

updates = []
for prop_id, ext_id in rows:
    if ext_id and ext_id.strip():
        code = ext_id.strip().upper()
        # Validar padrão básico
        if len(code) >= 2 and len(code) <= 10:
            updates.append((code, prop_id))

print(f"Atualizando {len(updates)} registros...")

for code, prop_id in updates:
    cursor.execute(
        "UPDATE re_properties SET ref_code = ? WHERE id = ?",
        (code, prop_id)
    )

conn.commit()
conn.close()

print(f"✅ Concluído: {len(updates)} ref_codes populados")

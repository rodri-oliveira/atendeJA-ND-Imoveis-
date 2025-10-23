import sqlite3
import time
import os
from pathlib import Path

# Remover locks órfãos
for f in ["dev.db-journal", "dev.db-shm", "dev.db-wal"]:
    try:
        os.remove(f)
    except:
        pass

time.sleep(1)

db = Path("dev.db")
conn = sqlite3.connect(str(db), timeout=60, isolation_level=None)
cursor = conn.cursor()

cursor.execute("SELECT id, external_id FROM re_properties WHERE (ref_code IS NULL OR ref_code = '') AND external_id IS NOT NULL")
rows = cursor.fetchall()

count = 0
for pid, ext_id in rows:
    if ext_id and 2 <= len(ext_id.strip()) <= 10:
        cursor.execute("UPDATE re_properties SET ref_code = ? WHERE id = ?", (ext_id.strip().upper(), pid))
        count += 1

conn.commit()
conn.close()
print(f"Atualizados: {count}")

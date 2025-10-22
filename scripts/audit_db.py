#!/usr/bin/env python3
"""Auditoria completa do banco de dados SQLite"""
import sqlite3
import os
from pathlib import Path

# Caminho do banco (um nível acima da pasta scripts)
db_path = Path(__file__).parent.parent / 'dev.db'

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 60)
print("📊 AUDITORIA DO BANCO DE DADOS")
print("=" * 60)

# Listar todas as tabelas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print(f"\n📋 Total de tabelas: {len(tables)}\n")

for (table_name,) in tables:
    # Contar registros
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    
    # Pegar estrutura
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"📦 {table_name}")
    print(f"   Registros: {count}")
    print(f"   Colunas: {len(columns)}")
    
    if count > 0:
        print(f"   ⚠️  TEM DADOS!")
    
    print()

# Verificar tabelas vazias
print("=" * 60)
print("🔍 ANÁLISE DE REDUNDÂNCIA")
print("=" * 60)

cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' 
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""")
all_tables = [t[0] for t in cursor.fetchall()]

empty_tables = []
for table in all_tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    if cursor.fetchone()[0] == 0:
        empty_tables.append(table)

if empty_tables:
    print(f"\n✅ Tabelas vazias (OK para dev): {len(empty_tables)}")
    for t in empty_tables:
        print(f"   - {t}")
else:
    print("\n⚠️  Todas as tabelas têm dados!")

# Verificar tabelas de leads
print("\n" + "=" * 60)
print("🎯 TABELAS DE LEADS")
print("=" * 60)

lead_tables = [t for t in all_tables if 'lead' in t.lower()]
for table in lead_tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"   {table}: {count} registros")

# Verificar tabelas de imóveis
print("\n" + "=" * 60)
print("🏠 TABELAS DE IMÓVEIS")
print("=" * 60)

property_tables = [t for t in all_tables if 'propert' in t.lower() or 'imovel' in t.lower()]
for table in property_tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"   {table}: {count} registros")

conn.close()

print("\n" + "=" * 60)
print("✅ AUDITORIA CONCLUÍDA")
print("=" * 60)

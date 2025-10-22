#!/usr/bin/env python3
"""Script para limpar todos os leads do banco SQLite"""
import sqlite3

# Conectar no banco
conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

# Ver quantos leads existem
cursor.execute('SELECT COUNT(*) FROM re_leads')
total = cursor.fetchone()[0]
print(f'📊 Total de leads antes: {total}')

# Deletar todos
cursor.execute('DELETE FROM re_leads')
conn.commit()

# Confirmar
cursor.execute('SELECT COUNT(*) FROM re_leads')
remaining = cursor.fetchone()[0]
print(f'✅ Leads deletados: {total}')
print(f'📊 Total de leads depois: {remaining}')

conn.close()
print('\n🎉 Banco limpo com sucesso!')

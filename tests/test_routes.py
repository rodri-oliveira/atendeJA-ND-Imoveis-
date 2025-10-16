"""
Testa se as rotas do MCP estão registradas corretamente.
"""
from app.main import app

# Listar todas as rotas
print("=== ROTAS REGISTRADAS ===")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ','.join(route.methods) if route.methods else 'N/A'
        print(f"{methods:10} {route.path}")

# Verificar rota específica
target = "/api/v1/mcp/admin/state/clear"
found = any(hasattr(r, 'path') and r.path == target for r in app.routes)

print(f"\n{'✅' if found else '❌'} Rota {target}: {'ENCONTRADA' if found else 'NÃO ENCONTRADA'}")

if not found:
    print("\n🔍 Rotas do MCP encontradas:")
    for route in app.routes:
        if hasattr(route, 'path') and '/mcp/' in route.path:
            methods = ','.join(route.methods) if hasattr(route, 'methods') and route.methods else 'N/A'
            print(f"  {methods:10} {route.path}")

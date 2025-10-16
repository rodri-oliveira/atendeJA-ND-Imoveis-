"""
Teste direto do endpoint de limpeza de estado.
Executa sem precisar do servidor rodando.
"""
from app.api.routes.mcp import mcp_admin_clear_state, ClearStateIn
from app.services.conversation_state import ConversationStateService
from app.core.config import settings
import redis

# Conectar no Redis
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

state_service = ConversationStateService(redis_client)

# Testar limpeza
payload = ClearStateIn(sender_ids=["5511964442592@c.us", "test@c.us"])
result = mcp_admin_clear_state(payload, state_service, Authorization=None)

print("Resultado:", result)
print("✅ Endpoint funciona corretamente!")

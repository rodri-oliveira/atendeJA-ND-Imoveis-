import json
from typing import Any, Dict, Optional

import redis

class ConversationStateService:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    def _get_key(self, sender_id: str, tenant_id: int | None = None) -> str:
        if tenant_id is None:
            return f"conversation_state:{sender_id}"
        return f"conversation_state:{int(tenant_id)}:{sender_id}"

    def get_state(self, sender_id: str, tenant_id: int | None = None) -> Optional[Dict[str, Any]]:
        """Recupera o estado da conversa.

        Compatibilidade retroativa:
        - Quando tenant_id é fornecido, tenta a chave nova (tenant-aware).
        - Se não existir, tenta a chave legada (sem tenant_id) e migra (copia) para a chave nova.
        """

        if tenant_id is not None:
            key = self._get_key(sender_id, tenant_id)
            state_json = self.redis_client.get(key)
            if state_json:
                return json.loads(state_json)

            legacy_key = self._get_key(sender_id, None)
            legacy_json = self.redis_client.get(legacy_key)
            if legacy_json:
                # Migração (cópia) para chave nova, mantendo a legada por compatibilidade.
                self.redis_client.setex(key, 3600, legacy_json)
                return json.loads(legacy_json)
            return None

        key = self._get_key(sender_id, None)
        state_json = self.redis_client.get(key)
        if state_json:
            return json.loads(state_json)
        return None

    def set_state(self, sender_id: str, state: Dict[str, Any], expiration_secs: int = 3600, tenant_id: int | None = None):
        """Define o estado da conversa.

        - Se tenant_id é fornecido, persiste na chave tenant-aware.
        - Caso contrário, usa a chave legada.
        """
        key = self._get_key(sender_id, tenant_id)
        state_json = json.dumps(state)
        self.redis_client.setex(key, expiration_secs, state_json)

    def clear_state(self, sender_id: str, tenant_id: int | None = None):
        """Limpa o estado da conversa.

        - Se tenant_id é fornecido, remove a chave tenant-aware.
        - Caso contrário, remove a chave legada.
        """
        key = self._get_key(sender_id, tenant_id)
        self.redis_client.delete(key)
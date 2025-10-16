import json
from typing import Any, Dict, Optional

import redis

class ConversationStateService:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    def _get_key(self, sender_id: str) -> str:
        return f"conversation_state:{sender_id}"

    def get_state(self, sender_id: str) -> Optional[Dict[str, Any]]:
        """Recupera o estado da conversa para um determinado sender_id."""
        key = self._get_key(sender_id)
        state_json = self.redis_client.get(key)
        if state_json:
            return json.loads(state_json)
        return None

    def set_state(self, sender_id: str, state: Dict[str, Any], expiration_secs: int = 3600):
        """Define o estado da conversa para um determinado sender_id."""
        key = self._get_key(sender_id)
        state_json = json.dumps(state)
        self.redis_client.setex(key, expiration_secs, state_json)

    def clear_state(self, sender_id: str):
        """Limpa o estado da conversa para um determinado sender_id."""
        key = self._get_key(sender_id)
        self.redis_client.delete(key)
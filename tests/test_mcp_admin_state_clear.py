from __future__ import annotations

from typing import Any, Dict, Optional

from app.main import app
from app.api.deps import get_conversation_state_service
from app.core.config import settings


class InMemoryConversationStateService:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def _key(self, sender_id: str, tenant_id: int | None = None) -> str:
        if tenant_id is None:
            return f"conversation_state:{sender_id}"
        return f"conversation_state:{int(tenant_id)}:{sender_id}"

    def get_state(self, sender_id: str, tenant_id: int | None = None) -> Optional[Dict[str, Any]]:
        return self._store.get(self._key(sender_id, tenant_id))

    def set_state(self, sender_id: str, state: Dict[str, Any], expiration_secs: int = 3600, tenant_id: int | None = None):
        _ = expiration_secs
        self._store[self._key(sender_id, tenant_id)] = dict(state)

    def clear_state(self, sender_id: str, tenant_id: int | None = None):
        self._store.pop(self._key(sender_id, tenant_id), None)


def test_mcp_admin_state_clear_clears_tenant_and_legacy_keys(client):
    state_service = InMemoryConversationStateService()

    def _override_state_service():
        return state_service

    app.dependency_overrides[get_conversation_state_service] = _override_state_service

    old_token = settings.MCP_API_TOKEN
    settings.MCP_API_TOKEN = ""

    try:
        sender_id = "5511999999999"

        # Arrange: create tenant-aware, legacy, and another tenant key
        state_service.set_state(sender_id, {"stage": "awaiting_lgpd_consent", "tenant_id": 1}, tenant_id=1)
        state_service.set_state(sender_id, {"stage": "legacy", "tenant_id": 999}, tenant_id=None)
        state_service.set_state(sender_id, {"stage": "other_tenant", "tenant_id": 2}, tenant_id=2)

        # Act
        resp = client.post(
            "/api/v1/mcp/admin/state/clear",
            json={"sender_ids": [sender_id], "tenant_id": 1},
        )

        # Assert
        assert resp.status_code == 200, resp.text
        assert resp.json().get("ok") is True

        assert state_service.get_state(sender_id, tenant_id=1) is None
        assert state_service.get_state(sender_id, tenant_id=None) is None
        # Must not delete other tenant
        assert (state_service.get_state(sender_id, tenant_id=2) or {}).get("stage") == "other_tenant"

    finally:
        settings.MCP_API_TOKEN = old_token
        app.dependency_overrides.clear()

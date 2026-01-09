from __future__ import annotations

import json

from app.domain.realestate.models import ChatbotFlow, Lead
from app.repositories import models as core_models
from app.api.deps import get_conversation_state_service


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def setex(self, key: str, _ttl: int, value: str):
        self._store[key] = value

    def delete(self, key: str):
        self._store.pop(key, None)


class InMemoryConversationStateService:
    def __init__(self):
        self._store: dict[str, dict[str, any]] = {}

    def _key(self, sender_id: str, tenant_id: int | None = None) -> str:
        if tenant_id is None:
            return f"conversation_state:{sender_id}"
        return f"conversation_state:{int(tenant_id)}:{sender_id}"

    def get_state(self, sender_id: str, tenant_id: int | None = None) -> dict[str, any] | None:
        return self._store.get(self._key(sender_id, tenant_id))

    def set_state(self, sender_id: str, state: dict[str, any], expiration_secs: int = 3600, tenant_id: int | None = None):
        _ = expiration_secs
        self._store[self._key(sender_id, tenant_id)] = dict(state)

    def clear_state(self, sender_id: str, tenant_id: int | None = None):
        self._store.pop(self._key(sender_id, tenant_id), None)


class _SessionLocalOverride:
    def __init__(self, db_session):
        self._db_session = db_session

    def __call__(self):
        return self

    def __enter__(self):
        return self._db_session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_e2e_publish_flow_and_webhook_consumes_it(client, db_session, monkeypatch):
    from app.api.routes import webhook as webhook_module

    fake_redis = _FakeRedis()
    monkeypatch.setattr(webhook_module, "_redis", lambda: fake_redis)
    monkeypatch.setattr(webhook_module, "SessionLocal", _SessionLocalOverride(db_session))

    # 1. Arrange: Create tenant and map phone number
    tenant_id = 15
    phone_number_id = "pnid-e2e"
    sender_id = "5511987654321"
    tenant = core_models.Tenant(id=tenant_id, name=f"tenant-{tenant_id}")
    db_session.add(tenant)
    db_session.commit()
    db_session.add(core_models.WhatsAppAccount(tenant_id=tenant_id, phone_number_id=phone_number_id, is_active=True))
    db_session.commit()

    # 2. Create and publish a flow via admin API
    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": [{"to": "awaiting_lgpd_consent"}]},
            {"id": "awaiting_lgpd_consent", "type": "handler", "handler": "lgpd_consent", "transitions": []},
        ],
    }
    headers = {"X-Tenant-Id": str(tenant_id)}
    r_create = client.post(
        "/admin/re/chatbot-flows",
        json={"name": "e2e-flow", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r_create.status_code == 200, r_create.text
    flow_id = r_create.json()["id"]

    r_publish = client.post(f"/admin/re/chatbot-flows/{flow_id}/publish", headers=headers)
    assert r_publish.status_code == 200, r_publish.text

    # 3. Act: Simulate webhook message for this tenant
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"wa_id": sender_id}],
                            "messages": [{"id": "msg-e2e", "from": sender_id, "type": "text", "text": {"body": "oi"}}],
                        }
                    }
                ]
            }
        ]
    }
    r_webhook = client.post("/webhook", json=payload)
    assert r_webhook.status_code == 200, r_webhook.text

    # 4. Assert: State was persisted correctly by the flow
    state_key = f"conversation_state:{tenant_id}:{sender_id}"
    raw_state = fake_redis.get(state_key)
    assert raw_state, "Expected state to be persisted in Redis"
    state = json.loads(raw_state)
    assert state.get("tenant_id") == tenant_id
    assert state.get("stage") == "awaiting_lgpd_consent"


def test_e2e_publish_flow_and_mcp_consumes_it_and_creates_lead(client, db_session):
    from app.main import app

    state_service = InMemoryConversationStateService()
    app.dependency_overrides[get_conversation_state_service] = lambda: state_service

    # 1. Arrange: Create tenant
    tenant_id = 25
    sender_id = "tester-mcp-e2e"
    tenant = core_models.Tenant(id=tenant_id, name=f"tenant-{tenant_id}")
    db_session.add(tenant)
    db_session.commit()

    # 2. Create and publish a flow that leads to lead creation
    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start"},
            {"id": "awaiting_lgpd_consent", "type": "handler", "handler": "lgpd_consent"},
            {"id": "awaiting_name", "type": "handler", "handler": "name"},
            {"id": "awaiting_schedule_visit_question", "type": "handler", "handler": "schedule_visit_question"},
        ],
    }
    headers = {"X-Tenant-Id": str(tenant_id)}
    r_create = client.post(
        "/admin/re/chatbot-flows",
        json={"name": "mcp-e2e-flow", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r_create.status_code == 200, r_create.text
    flow_id = r_create.json()["id"]

    r_publish = client.post(f"/admin/re/chatbot-flows/{flow_id}/publish", headers=headers)
    assert r_publish.status_code == 200, r_publish.text

    # 3. Act: Simulate MCP conversation that creates a lead
    # Manually set state to bypass full conversation script
    state_service.set_state(
        sender_id,
        {"stage": "awaiting_schedule_visit_question", "user_name": "E2E Test", "tenant_id": tenant_id},
        tenant_id=tenant_id,
    )

    body = {"input": "não", "sender_id": sender_id, "tenant_id": str(tenant_id), "mode": "auto"}
    r_mcp = client.post("/api/v1/mcp/execute", json=body)
    assert r_mcp.status_code == 200, r_mcp.text

    # 4. Assert: Lead was created with the correct tenant_id
    lead = (
        db_session.query(Lead)
        .filter(Lead.name == "E2E Test", Lead.tenant_id == tenant_id)
        .order_by(Lead.id.desc())
        .first()
    )
    assert lead is not None
    assert int(lead.tenant_id) == tenant_id

    app.dependency_overrides.clear()

from __future__ import annotations

import json

from app.main import app
from app.domain.realestate.models import ChatbotFlow
from app.repositories import models as core_models


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def setex(self, key: str, _ttl: int, value: str):
        self._store[key] = value

    def set(self, key: str, value: str):
        self._store[key] = value

    def delete(self, key: str):
        self._store.pop(key, None)


class _SessionLocalOverride:
    def __init__(self, db_session):
        self._db_session = db_session

    def __call__(self):
        return self

    def __enter__(self):
        return self._db_session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_webhook_uses_flow_engine_and_persists_state(client, db_session, monkeypatch):
    from app.api.routes import webhook as webhook_module

    fake_redis = _FakeRedis()
    monkeypatch.setattr(webhook_module, "_redis", lambda: fake_redis)
    monkeypatch.setattr(webhook_module, "SessionLocal", _SessionLocalOverride(db_session))

    # Arrange: tenant + WhatsApp account mapping
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
        db_session.commit()

    acct = core_models.WhatsAppAccount(tenant_id=1, phone_number_id="pnid-1", is_active=True)
    db_session.add(acct)
    db_session.commit()

    # Arrange: flow publicado para tenant 1
    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {
                "id": "start",
                "type": "handler",
                "handler": "start",
                "transitions": [{"to": "awaiting_lgpd_consent"}],
            },
            {
                "id": "awaiting_lgpd_consent",
                "type": "handler",
                "handler": "lgpd_consent",
                "transitions": [],
            },
        ],
    }
    db_session.add(
        ChatbotFlow(
            tenant_id=1,
            domain="real_estate",
            name="default-test-webhook",
            flow_definition=flow_definition,
            is_published=True,
            published_version=1,
            published_by="test",
        )
    )
    db_session.commit()

    sender = "5561999999999"

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "pnid-1"},
                            "contacts": [{"wa_id": sender}],
                            "messages": [
                                {
                                    "id": "msg-001",
                                    "from": sender,
                                    "type": "text",
                                    "text": {"body": "oi"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    # Act
    resp = client.post("/webhook", json=payload)

    # Assert
    assert resp.status_code == 200
    assert resp.json().get("received") is True

    key = f"conversation_state:1:{sender}"
    raw = fake_redis.get(key)
    assert raw, "expected state to be persisted in redis"
    state = json.loads(raw)
    assert state.get("tenant_id") == 1
    assert state.get("stage") == "awaiting_lgpd_consent"

    app.dependency_overrides.clear()


def test_webhook_same_wa_id_does_not_collide_between_tenants(client, db_session, monkeypatch):
    from app.api.routes import webhook as webhook_module

    fake_redis = _FakeRedis()
    monkeypatch.setattr(webhook_module, "_redis", lambda: fake_redis)
    monkeypatch.setattr(webhook_module, "SessionLocal", _SessionLocalOverride(db_session))

    # Arrange: two tenants with different phone_number_id mapping
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
    if db_session.get(core_models.Tenant, 2) is None:
        db_session.add(core_models.Tenant(id=2, name="tenant-2"))
    db_session.commit()

    db_session.add_all(
        [
            core_models.WhatsAppAccount(tenant_id=1, phone_number_id="pnid-1", is_active=True),
            core_models.WhatsAppAccount(tenant_id=2, phone_number_id="pnid-2", is_active=True),
        ]
    )
    db_session.commit()

    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": [{"to": "awaiting_lgpd_consent"}]},
            {"id": "awaiting_lgpd_consent", "type": "handler", "handler": "lgpd_consent", "transitions": []},
        ],
    }
    db_session.add_all(
        [
            ChatbotFlow(
                tenant_id=1,
                domain="real_estate",
                name="default-test-webhook-1",
                flow_definition=flow_definition,
                is_published=True,
                published_version=1,
                published_by="test",
            ),
            ChatbotFlow(
                tenant_id=2,
                domain="real_estate",
                name="default-test-webhook-2",
                flow_definition=flow_definition,
                is_published=True,
                published_version=1,
                published_by="test",
            ),
        ]
    )
    db_session.commit()

    sender = "5561999999999"

    payload_1 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "pnid-1"},
                            "contacts": [{"wa_id": sender}],
                            "messages": [
                                {"id": "msg-101", "from": sender, "type": "text", "text": {"body": "oi"}}
                            ],
                        }
                    }
                ]
            }
        ]
    }

    payload_2 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "pnid-2"},
                            "contacts": [{"wa_id": sender}],
                            "messages": [
                                {"id": "msg-201", "from": sender, "type": "text", "text": {"body": "oi"}}
                            ],
                        }
                    }
                ]
            }
        ]
    }

    r1 = client.post("/webhook", json=payload_1)
    assert r1.status_code == 200
    r2 = client.post("/webhook", json=payload_2)
    assert r2.status_code == 200

    raw1 = fake_redis.get(f"conversation_state:1:{sender}")
    raw2 = fake_redis.get(f"conversation_state:2:{sender}")
    assert raw1 and raw2

    s1 = json.loads(raw1)
    s2 = json.loads(raw2)
    assert s1.get("tenant_id") == 1
    assert s2.get("tenant_id") == 2
    assert s1.get("stage") == "awaiting_lgpd_consent"
    assert s2.get("stage") == "awaiting_lgpd_consent"

    app.dependency_overrides.clear()

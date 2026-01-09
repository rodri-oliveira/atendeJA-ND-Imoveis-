from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.main import app
from app.api.deps import get_conversation_state_service
from app.domain.realestate.models import ChatbotFlow, Lead


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


def _override_state_service(state_service: InMemoryConversationStateService):
    def _override():
        return state_service

    app.dependency_overrides[get_conversation_state_service] = _override


def test_flow_engine_advances_start_to_lgpd(client, db_session: Session):
    state_service = InMemoryConversationStateService()
    _override_state_service(state_service)

    # Arrange: cria flow publicado para tenant 1
    existing = (
        db_session.query(ChatbotFlow)
        .filter(
            ChatbotFlow.tenant_id == 1,
            ChatbotFlow.domain == "real_estate",
            ChatbotFlow.is_published == True,  # noqa: E712
        )
        .first()
    )
    if not existing:
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
                name="default-test",
                flow_definition=flow_definition,
                is_published=True,
                published_version=1,
                published_by="test",
            )
        )
        db_session.commit()

    # Act
    body = {
        "input": "oi",
        "sender_id": "tester-flow-001",
        "tenant_id": "1",
        "mode": "auto",
    }
    r = client.post("/api/v1/mcp/execute", json=body)

    # Assert
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("message"), str)

    st = state_service.get_state("tester-flow-001", tenant_id=1) or {}
    assert st.get("stage") == "awaiting_lgpd_consent"

    app.dependency_overrides.clear()


def test_lgpd_is_deterministic_and_tenant_isolation_on_lead_creation(client, db_session: Session):
    state_service = InMemoryConversationStateService()
    _override_state_service(state_service)

    sender_id = "5511990000000@c.us"

    # Arrange: estado já no estágio de LGPD e com tenant 2
    state_service.set_state(
        sender_id,
        {
            "stage": "awaiting_lgpd_consent",
            "sender_id": sender_id,
            "tenant_id": 2,
        },
        tenant_id=2,
    )

    # 1) Entrada inválida não deve avançar
    r1 = client.post(
        "/api/v1/mcp/execute",
        json={"input": "talvez", "sender_id": sender_id, "tenant_id": "2", "mode": "auto"},
    )
    assert r1.status_code == 200, r1.text
    st1 = state_service.get_state(sender_id, tenant_id=2) or {}
    assert st1.get("stage") == "awaiting_lgpd_consent"

    # 2) Consentimento válido deve avançar
    r2 = client.post(
        "/api/v1/mcp/execute",
        json={"input": "sim", "sender_id": sender_id, "tenant_id": "2", "mode": "auto"},
    )
    assert r2.status_code == 200, r2.text
    st2 = state_service.get_state(sender_id, tenant_id=2) or {}
    assert st2.get("tenant_id") == 2
    assert st2.get("stage") in {"awaiting_name", "awaiting_purpose", "awaiting_has_property_in_mind"}

    # Arrange: agora forçar um estágio que cria lead via upsert (sem depender do fluxo inteiro)
    state_service.set_state(
        sender_id,
        {
            "stage": "awaiting_schedule_visit_question",
            "sender_id": sender_id,
            "tenant_id": 2,
            "user_name": "Teste",
        },
        tenant_id=2,
    )

    r3 = client.post(
        "/api/v1/mcp/execute",
        json={"input": "não", "sender_id": sender_id, "tenant_id": "2", "mode": "auto"},
    )
    assert r3.status_code == 200, r3.text

    lead = (
        db_session.query(Lead)
        .filter(Lead.phone == "5511990000000", Lead.tenant_id == 2)
        .order_by(Lead.id.desc())
        .first()
    )
    assert lead is not None

    app.dependency_overrides.clear()

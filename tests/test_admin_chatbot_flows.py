from __future__ import annotations

from app.domain.realestate.models import ChatbotFlow
from app.repositories import models as core_models


def test_admin_chatbot_flow_create_and_publish_and_mcp_consumes(client, db_session):
    # Arrange: tenant required by require_active_tenant
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
        db_session.commit()

    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": [{"to": "awaiting_lgpd_consent"}]},
            {"id": "awaiting_lgpd_consent", "type": "handler", "handler": "lgpd_consent", "transitions": []},
        ],
    }

    headers = {"X-Tenant-Id": "1"}

    # 1) Create/update flow
    r1 = client.post(
        "/admin/re/chatbot-flows",
        json={"domain": "real_estate", "name": "flow-a", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    flow_id = r1.json()["id"]

    # 2) Publish flow
    r2 = client.post(f"/admin/re/chatbot-flows/{flow_id}/publish", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True

    published = (
        db_session.query(ChatbotFlow)
        .filter(ChatbotFlow.tenant_id == 1, ChatbotFlow.domain == "real_estate", ChatbotFlow.is_published == True)  # noqa: E712
        .first()
    )
    assert published is not None
    assert int(published.id) == int(flow_id)
    assert int(published.published_version) >= 1

    # 3) MCP should consume published flow
    body = {"input": "oi", "sender_id": "tester-admin-flow", "tenant_id": "1", "mode": "auto"}
    r3 = client.post("/api/v1/mcp/execute", json=body)
    assert r3.status_code == 200, r3.text


def test_admin_chatbot_flow_list(client, db_session):
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
        db_session.commit()

    db_session.add(
        ChatbotFlow(
            tenant_id=1,
            domain="real_estate",
            name="flow-list",
            flow_definition={"version": 1, "start": "start", "nodes": []},
            is_published=False,
            published_version=0,
        )
    )
    db_session.commit()

    r = client.get("/admin/re/chatbot-flows", headers={"X-Tenant-Id": "1"})
    assert r.status_code == 200, r.text
    assert any(x.get("name") == "flow-list" for x in r.json())


def test_admin_chatbot_flow_rollback_by_version(client, db_session):
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
        db_session.commit()

    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": [{"to": "awaiting_lgpd_consent"}]},
            {"id": "awaiting_lgpd_consent", "type": "handler", "handler": "lgpd_consent", "transitions": []},
        ],
    }

    headers = {"X-Tenant-Id": "1"}

    r1 = client.post(
        "/admin/re/chatbot-flows",
        json={"domain": "real_estate", "name": "flow-v1", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    flow_v1_id = int(r1.json()["id"])

    r2 = client.post(f"/admin/re/chatbot-flows/{flow_v1_id}/publish", headers=headers)
    assert r2.status_code == 200, r2.text
    v1 = int(r2.json().get("published_version") or 0)
    assert v1 >= 1

    r3 = client.post(
        "/admin/re/chatbot-flows",
        json={"domain": "real_estate", "name": "flow-v2", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r3.status_code == 200, r3.text
    flow_v2_id = int(r3.json()["id"])

    r4 = client.post(f"/admin/re/chatbot-flows/{flow_v2_id}/publish", headers=headers)
    assert r4.status_code == 200, r4.text
    v2 = int(r4.json().get("published_version") or 0)
    assert v2 == v1 + 1

    # published current should be v2 now
    current = client.get("/admin/re/chatbot-flows/published", headers=headers)
    assert current.status_code == 200, current.text
    assert current.json().get("published") is True
    assert (current.json().get("flow") or {}).get("id") == flow_v2_id

    # rollback to v1
    rb = client.post(
        "/admin/re/chatbot-flows/publish-by-version",
        json={"domain": "real_estate", "published_version": v1},
        headers=headers,
    )
    assert rb.status_code == 200, rb.text
    assert int(rb.json().get("published_version") or 0) == v1

    current2 = client.get("/admin/re/chatbot-flows/published", headers=headers)
    assert current2.status_code == 200, current2.text
    assert (current2.json().get("flow") or {}).get("id") == flow_v1_id

    row1 = db_session.get(ChatbotFlow, flow_v1_id)
    row2 = db_session.get(ChatbotFlow, flow_v2_id)
    assert bool(getattr(row1, "is_published", False)) is True
    assert bool(getattr(row2, "is_published", False)) is False

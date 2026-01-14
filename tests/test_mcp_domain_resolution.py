from __future__ import annotations

from app.repositories import models as core_models


def test_mcp_uses_tenant_domain_flow(client, db_session):
    tenant = db_session.get(core_models.Tenant, 1)
    if tenant is None:
        tenant = core_models.Tenant(id=1, name="tenant-1")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    tenant.settings_json = {"chatbot_domain": "car_dealer"}
    db_session.add(tenant)
    db_session.commit()

    headers = {"X-Tenant-Id": "1"}
    r1 = client.post(
        "/admin/chatbot-templates/apply",
        json={"domain": "car_dealer", "template": "default", "name": "default", "overwrite": True, "publish": True},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    body = {"input": "oi", "sender_id": "tester-domain", "tenant_id": "1", "mode": "auto"}
    r2 = client.post("/api/v1/mcp/execute", json=body)
    assert r2.status_code == 200, r2.text
    assert "Atendimento Auto" in (r2.json().get("message") or "")

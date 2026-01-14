from __future__ import annotations

from app.repositories import models as core_models


def test_admin_get_and_set_chatbot_domain(client, db_session):
    tenant = db_session.get(core_models.Tenant, 1)
    if tenant is None:
        tenant = core_models.Tenant(id=1, name="tenant-1")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    # default fallback
    r1 = client.get("/admin/chatbot-domain", headers={"X-Tenant-Id": "1"})
    assert r1.status_code == 200, r1.text
    assert (r1.json().get("domain") or "") in {"real_estate", "car_dealer"}

    r2 = client.put(
        "/admin/chatbot-domain",
        json={"domain": "car_dealer"},
        headers={"X-Tenant-Id": "1"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("domain") == "car_dealer"

    # persisted
    r3 = client.get("/admin/chatbot-domain", headers={"X-Tenant-Id": "1"})
    assert r3.status_code == 200, r3.text
    assert r3.json().get("domain") == "car_dealer"

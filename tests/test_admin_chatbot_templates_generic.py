from __future__ import annotations

from app.domain.realestate.models import ChatbotFlow
from app.repositories import models as core_models


def test_admin_chatbot_templates_generic_list_and_apply(client, db_session):
    if db_session.get(core_models.Tenant, 1) is None:
        db_session.add(core_models.Tenant(id=1, name="tenant-1"))
        db_session.commit()

    headers = {"X-Tenant-Id": "1"}

    r1 = client.get("/admin/chatbot-templates", headers=headers)
    assert r1.status_code == 200, r1.text
    assert any(x.get("domain") == "real_estate" and x.get("template") == "default" for x in r1.json())

    r2 = client.post(
        "/admin/chatbot-templates/apply",
        json={"domain": "car_dealer", "template": "default", "name": "default", "overwrite": True, "publish": True},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    flow_id = int(r2.json().get("flow_id") or 0)
    assert flow_id > 0

    published = (
        db_session.query(ChatbotFlow)
        .filter(ChatbotFlow.tenant_id == 1, ChatbotFlow.domain == "car_dealer", ChatbotFlow.is_published == True)  # noqa: E712
        .first()
    )
    assert published is not None
    assert int(published.id) == flow_id

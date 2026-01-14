from __future__ import annotations


def test_super_onboarding_by_url_creates_tenant_and_published_flow(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant Auto 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
        },
        headers=headers,
    )

    assert r.status_code == 200, r.text
    js = r.json()

    assert int(js.get("tenant_id") or 0) > 0
    assert js.get("tenant_name") == "Tenant Auto 1"
    assert js.get("chatbot_domain") == "car_dealer"
    assert int(js.get("flow_id") or 0) > 0
    assert js.get("published") is True
    assert js.get("published_version") is not None

    # sanity: calling again with same name must fail
    r2 = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant Auto 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
        },
        headers=headers,
    )
    assert r2.status_code == 400
    payload2 = r2.json() or {}
    # API pode retornar {"detail": ...} ou envelope {"error": {"code": ...}}
    assert (
        payload2.get("detail") == "tenant_name_already_exists"
        or (payload2.get("error") or {}).get("code") == "tenant_name_already_exists"
    )

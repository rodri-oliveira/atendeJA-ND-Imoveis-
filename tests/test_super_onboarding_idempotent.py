from __future__ import annotations


def test_super_onboarding_by_url_allow_existing_is_idempotent(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant Idempotent 1",
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
    assert r1.status_code == 200, r1.text
    js1 = r1.json() or {}

    r2 = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant Idempotent 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": True,
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}

    assert js2.get("tenant_id") == js1.get("tenant_id")
    assert js2.get("chatbot_domain") == "car_dealer"
    assert int(js2.get("flow_id") or 0) > 0
    assert js2.get("published") is True

from __future__ import annotations


def test_super_onboarding_by_url_idempotency_key_replays_result(client):
    headers = {"X-Super-Admin-Key": "dev"}

    key = "key-abc-123"
    payload = {
        "idempotency_key": key,
        "name": "Tenant Key 1",
        "timezone": "America/Sao_Paulo",
        "chatbot_domain": "car_dealer",
        "allow_existing": False,
        "template": "default",
        "flow_name": "default",
        "overwrite_flow": True,
        "publish_flow": True,
        "run_ingestion": False,
    }

    r1 = client.post("/super/onboarding/by-url", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    js1 = r1.json() or {}

    r2 = client.post("/super/onboarding/by-url", json=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}

    assert js2.get("tenant_id") == js1.get("tenant_id")
    assert js2.get("flow_id") == js1.get("flow_id")


def test_super_onboarding_by_url_idempotency_key_conflict(client):
    headers = {"X-Super-Admin-Key": "dev"}

    key = "key-abc-999"
    payload1 = {
        "idempotency_key": key,
        "name": "Tenant Key 2",
        "timezone": "America/Sao_Paulo",
        "chatbot_domain": "car_dealer",
        "template": "default",
        "flow_name": "default",
        "overwrite_flow": True,
        "publish_flow": True,
        "run_ingestion": False,
    }
    payload2 = {
        "idempotency_key": key,
        "name": "Tenant Key 2 DIFFERENT",
        "timezone": "America/Sao_Paulo",
        "chatbot_domain": "car_dealer",
        "template": "default",
        "flow_name": "default",
        "overwrite_flow": True,
        "publish_flow": True,
        "run_ingestion": False,
    }

    r1 = client.post("/super/onboarding/by-url", json=payload1, headers=headers)
    assert r1.status_code == 200, r1.text

    r2 = client.post("/super/onboarding/by-url", json=payload2, headers=headers)
    assert r2.status_code == 409, r2.text
    js2 = r2.json() or {}
    assert js2.get("detail") == "idempotency_key_conflict" or (js2.get("error") or {}).get("code") == "idempotency_key_conflict"

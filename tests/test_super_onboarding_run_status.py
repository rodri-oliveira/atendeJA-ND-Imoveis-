from __future__ import annotations


def test_super_can_get_onboarding_run_by_idempotency_key(client):
    headers = {"X-Super-Admin-Key": "dev"}

    key = "run-status-1"
    r = client.post(
        "/super/onboarding/by-url",
        json={
            "idempotency_key": key,
            "name": "Tenant Run Status 1",
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

    r2 = client.get(f"/super/onboarding-runs/{key}", headers=headers)
    assert r2.status_code == 200, r2.text
    js = r2.json() or {}
    assert js.get("idempotency_key") == key
    assert js.get("status") == "completed"
    assert js.get("tenant_id")
    assert js.get("request_json")
    assert js.get("response_json")
    assert "invite_token" not in (js.get("response_json") or {})


def test_super_onboarding_run_records_error_code(client):
    headers = {"X-Super-Admin-Key": "dev"}

    # Primeiro cria WA com pnid
    r = client.post(
        "/super/onboarding/by-url",
        json={
            "idempotency_key": "wa-ok-1",
            "name": "Tenant WA OK",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "create_whatsapp_account": True,
            "phone_number_id": "pnid-run-1",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # Agora falha por pnid duplicado
    key = "wa-fail-1"
    r2 = client.post(
        "/super/onboarding/by-url",
        json={
            "idempotency_key": key,
            "name": "Tenant WA FAIL",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "create_whatsapp_account": True,
            "phone_number_id": "pnid-run-1",
        },
        headers=headers,
    )
    assert r2.status_code == 400, r2.text

    r3 = client.get(f"/super/onboarding-runs/{key}", headers=headers)
    assert r3.status_code == 200, r3.text
    js3 = r3.json() or {}
    assert js3.get("status") == "failed"
    assert js3.get("error_code") == "phone_number_id_already_exists"
    assert "invite_token" not in (js3.get("response_json") or {})

from __future__ import annotations


def test_super_onboarding_by_url_can_create_whatsapp_account(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant WA 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "create_whatsapp_account": True,
            "phone_number_id": "pnid-123",
            "waba_id": "waba-1",
            "token": "tok-1",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    js = r.json()
    assert js.get("tenant_id")
    assert js.get("whatsapp_account_id")

    # Repetir com o mesmo phone_number_id deve falhar por unique
    r2 = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant WA 2",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "create_whatsapp_account": True,
            "phone_number_id": "pnid-123",
        },
        headers=headers,
    )
    assert r2.status_code == 400, r2.text
    payload2 = r2.json() or {}
    assert (
        payload2.get("detail") == "phone_number_id_already_exists"
        or (payload2.get("error") or {}).get("code") == "phone_number_id_already_exists"
    )

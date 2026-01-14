from __future__ import annotations


def test_super_onboarding_step_ensure_tenant_creates_or_reuses(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": False,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    js1 = r1.json() or {}
    assert int(js1.get("tenant_id") or 0) > 0
    assert js1.get("tenant_name") == "Tenant Step 1"
    assert js1.get("chatbot_domain") == "car_dealer"

    r2 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": True,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    assert js2.get("tenant_id") == js1.get("tenant_id")


def test_super_onboarding_step_apply_flow_template_publishes(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step 2",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": False,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    tenant_id = int((r1.json() or {}).get("tenant_id") or 0)
    assert tenant_id > 0

    r2 = client.post(
        f"/super/onboarding/steps/tenants/{tenant_id}/apply-flow-template",
        json={
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    assert js2.get("tenant_id") == tenant_id
    assert js2.get("chatbot_domain") == "car_dealer"
    assert int(js2.get("flow_id") or 0) > 0
    assert js2.get("published") is True
    assert js2.get("published_version") is not None


def test_super_onboarding_step_create_whatsapp_account(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step WA",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": False,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    tenant_id = int((r1.json() or {}).get("tenant_id") or 0)
    assert tenant_id > 0

    r2 = client.post(
        f"/super/onboarding/steps/tenants/{tenant_id}/create-whatsapp-account",
        json={
            "phone_number_id": "pnid-step-1",
            "waba_id": "waba-1",
            "token": "token-1",
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    assert js2.get("tenant_id") == tenant_id
    assert int(js2.get("whatsapp_account_id") or 0) > 0
    assert js2.get("phone_number_id") == "pnid-step-1"


def test_super_onboarding_step_invite_admin(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step Invite",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": False,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    tenant_id = int((r1.json() or {}).get("tenant_id") or 0)
    assert tenant_id > 0

    r2 = client.post(
        f"/super/onboarding/steps/tenants/{tenant_id}/invite-admin",
        json={
            "email": "admin.step@example.com",
            "expires_hours": 72,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    assert js2.get("tenant_id") == tenant_id
    assert js2.get("email") == "admin.step@example.com"
    assert js2.get("token")


def test_super_onboarding_step_enqueue_ingestion_queues_run(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r1 = client.post(
        "/super/onboarding/steps/ensure-tenant",
        json={
            "name": "Tenant Step Ingestion",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "allow_existing": False,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    tenant_id = int((r1.json() or {}).get("tenant_id") or 0)
    assert tenant_id > 0

    r2 = client.post(
        f"/super/onboarding/steps/tenants/{tenant_id}/enqueue-ingestion",
        json={
            "base_url": "https://example.com",
            "max_listings": 10,
            "timeout_seconds": 5.0,
            "max_listing_pages": 1,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    assert js2.get("tenant_id") == tenant_id
    assert int(js2.get("run_id") or 0) > 0
    assert js2.get("status") == "queued"

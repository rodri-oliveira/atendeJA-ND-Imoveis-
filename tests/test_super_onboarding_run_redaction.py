from __future__ import annotations


def test_onboarding_run_redacts_invite_token_but_replay_still_returns_token(client):
    headers = {"X-Super-Admin-Key": "dev"}

    key = "invite-redact-1"
    r = client.post(
        "/super/onboarding/by-url",
        json={
            "idempotency_key": key,
            "name": "Tenant Invite Redact",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "invite_admin_email": "admin+redact@exemplo.com",
            "invite_expires_hours": 24,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    js = r.json() or {}
    assert js.get("invite_token")

    r2 = client.get(f"/super/onboarding-runs/{key}", headers=headers)
    assert r2.status_code == 200, r2.text
    js2 = r2.json() or {}
    resp = js2.get("response_json") or {}
    assert resp.get("invite_email") == "admin+redact@exemplo.com"
    assert "invite_token" not in resp

    # Replay: same request should still return token (reconstruído do user_invites)
    r3 = client.post(
        "/super/onboarding/by-url",
        json={
            "idempotency_key": key,
            "name": "Tenant Invite Redact",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "car_dealer",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "invite_admin_email": "admin+redact@exemplo.com",
            "invite_expires_hours": 24,
        },
        headers=headers,
    )
    assert r3.status_code == 200, r3.text
    js3 = r3.json() or {}
    assert js3.get("invite_token")
    assert js3.get("invite_email") == "admin+redact@exemplo.com"

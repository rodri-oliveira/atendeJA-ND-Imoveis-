from __future__ import annotations


def test_super_onboarding_by_url_can_invite_admin(client):
    headers = {"X-Super-Admin-Key": "dev"}

    r = client.post(
        "/super/onboarding/by-url",
        json={
            "name": "Tenant Invite 1",
            "timezone": "America/Sao_Paulo",
            "chatbot_domain": "real_estate",
            "template": "default",
            "flow_name": "default",
            "overwrite_flow": True,
            "publish_flow": True,
            "run_ingestion": False,
            "invite_admin_email": "admin+invite1@exemplo.com",
            "invite_expires_hours": 24,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    js = r.json() or {}
    assert js.get("tenant_id")
    assert js.get("invite_token")
    assert js.get("invite_email") == "admin+invite1@exemplo.com"

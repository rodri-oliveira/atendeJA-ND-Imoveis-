from __future__ import annotations


def test_super_chatbot_templates_lists_available(client):
    headers = {"X-Super-Admin-Key": "dev"}
    r = client.get("/super/chatbot-templates", headers=headers)
    assert r.status_code == 200, r.text
    js = r.json()
    assert isinstance(js, list)
    assert any(x.get("domain") == "real_estate" and x.get("template") == "default" for x in js)

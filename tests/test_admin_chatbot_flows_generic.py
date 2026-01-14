from __future__ import annotations


def test_admin_chatbot_flows_generic_crud_smoke(client):
    headers = {"X-Tenant-Id": "1"}

    r_tpl = client.post(
        "/admin/chatbot-flows/create-from-template",
        json={"domain": "car_dealer", "template": "default", "name": "tpl-flow", "overwrite": True, "publish": False},
        headers=headers,
    )
    assert r_tpl.status_code == 200, r_tpl.text
    tpl_flow_id = int(r_tpl.json().get("flow_id") or 0)
    assert tpl_flow_id > 0

    r_tpl_del = client.delete(f"/admin/chatbot-flows/{tpl_flow_id}", headers=headers)
    assert r_tpl_del.status_code == 200, r_tpl_del.text

    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": []},
        ],
    }

    r1 = client.post(
        "/admin/chatbot-flows",
        json={"domain": "car_dealer", "name": "flow-a", "flow_definition": flow_definition},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    flow_id = int(r1.json()["id"])

    r_clone = client.post(
        f"/admin/chatbot-flows/{flow_id}/clone",
        json={"name": "flow-a-copy", "overwrite": True, "publish": False},
        headers=headers,
    )
    assert r_clone.status_code == 200, r_clone.text
    cloned_id = int(r_clone.json().get("new_flow_id") or 0)
    assert cloned_id > 0

    r_arch = client.post(f"/admin/chatbot-flows/{cloned_id}/archive", headers=headers)
    assert r_arch.status_code == 200, r_arch.text
    assert r_arch.json().get("is_archived") is True

    r_list_default = client.get("/admin/chatbot-flows", params={"domain": "car_dealer"}, headers=headers)
    assert r_list_default.status_code == 200, r_list_default.text
    assert all(x.get("id") != cloned_id for x in r_list_default.json())

    r_list_all = client.get(
        "/admin/chatbot-flows",
        params={"domain": "car_dealer", "include_archived": True},
        headers=headers,
    )
    assert r_list_all.status_code == 200, r_list_all.text
    assert any(x.get("id") == cloned_id for x in r_list_all.json())

    r_unarch = client.post(f"/admin/chatbot-flows/{cloned_id}/unarchive", headers=headers)
    assert r_unarch.status_code == 200, r_unarch.text
    assert r_unarch.json().get("is_archived") is False

    r_key2 = client.get(
        "/admin/chatbot-flows/by-key",
        params={"domain": "car_dealer", "name": "flow-a-copy"},
        headers=headers,
    )
    assert r_key2.status_code == 200, r_key2.text
    assert (r_key2.json().get("flow_definition") or {}).get("start") == "start"

    r_get = client.get(f"/admin/chatbot-flows/by-id/{flow_id}", headers=headers)
    assert r_get.status_code == 200, r_get.text
    assert (r_get.json().get("flow_definition") or {}).get("start") == "start"

    r_key = client.get(
        "/admin/chatbot-flows/by-key",
        params={"domain": "car_dealer", "name": "flow-a"},
        headers=headers,
    )
    assert r_key.status_code == 200, r_key.text
    assert (r_key.json().get("flow_definition") or {}).get("start") == "start"

    r2 = client.post(f"/admin/chatbot-flows/{flow_id}/publish", headers=headers)
    assert r2.status_code == 200, r2.text
    assert int(r2.json().get("published_version") or 0) >= 1

    r_del_blocked = client.delete(f"/admin/chatbot-flows/{flow_id}", headers=headers)
    assert r_del_blocked.status_code == 409, r_del_blocked.text

    r3 = client.get("/admin/chatbot-flows/published", params={"domain": "car_dealer"}, headers=headers)
    assert r3.status_code == 200, r3.text
    assert r3.json().get("published") is True
    assert (r3.json().get("flow") or {}).get("id") == flow_id

    r4 = client.post(
        f"/admin/chatbot-flows/{flow_id}/preview",
        json={"sender_id": "preview", "input": "oi", "state": {"stage": "start"}},
        headers=headers,
    )
    assert r4.status_code == 200, r4.text
    assert r4.json().get("handled") is True
    assert "Car Dealer" in (r4.json().get("message") or "")

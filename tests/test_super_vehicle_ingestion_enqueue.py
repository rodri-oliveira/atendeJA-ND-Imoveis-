from __future__ import annotations


def test_super_vehicle_ingestion_enqueue_creates_queued_run(client):
    headers = {"X-Super-Admin-Key": "dev"}

    # create a tenant first
    r = client.post("/super/tenants", json={"name": "Tenant Ingest Q", "timezone": "America/Sao_Paulo"}, headers=headers)
    assert r.status_code == 200, r.text
    tenant_id = r.json()["id"]

    r2 = client.post(
        f"/super/tenants/{tenant_id}/ingestion/vehicles/enqueue",
        json={
            "base_url": "https://example.com/",
            "max_listings": 10,
            "timeout_seconds": 5,
            "max_listing_pages": 1,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    js = r2.json() or {}
    assert int(js.get("run_id") or 0) > 0
    assert js.get("status") == "queued"

    r3 = client.get(f"/super/tenants/{tenant_id}/ingestion/runs/{js['run_id']}", headers=headers)
    assert r3.status_code == 200, r3.text
    js3 = r3.json() or {}
    assert js3.get("status") == "queued"

from __future__ import annotations


def test_admin_catalog_item_type_and_item_crud_with_schema_validation(client):
    headers = {"X-Tenant-Id": "1"}

    # Create item type with schema
    r1 = client.post(
        "/admin/catalog/item-types",
        json={
            "key": "product",
            "name": "Produtos",
            "schema": {
                "fields": [
                    {"key": "price", "label": "Preço", "type": "number", "required": True},
                    {"key": "color", "label": "Cor", "type": "string", "required": False},
                ]
            },
            "is_active": True,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    it = r1.json() or {}
    assert it.get("key") == "product"
    assert int(it.get("id") or 0) > 0

    # Create item with valid attrs
    r2 = client.post(
        "/admin/catalog/items",
        json={
            "item_type_key": "product",
            "title": "Camiseta",
            "description": "Algodão",
            "attributes": {"price": 10.5, "color": "blue"},
            "is_active": True,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    item = r2.json() or {}
    assert item.get("title") == "Camiseta"
    assert item.get("attributes", {}).get("price") == 10.5

    # Reject unknown attribute
    r3 = client.post(
        "/admin/catalog/items",
        json={
            "item_type_key": "product",
            "title": "Camiseta 2",
            "attributes": {"price": 10.5, "unknown": "x"},
            "is_active": True,
        },
        headers=headers,
    )
    assert r3.status_code == 400
    js3 = r3.json() or {}
    assert (
        str(js3.get("detail") or "").startswith("unknown_attribute")
        or str((js3.get("error") or {}).get("code") or "").startswith("unknown_attribute")
    )

    # Reject missing required
    r4 = client.post(
        "/admin/catalog/items",
        json={
            "item_type_key": "product",
            "title": "Camiseta 3",
            "attributes": {"color": "red"},
            "is_active": True,
        },
        headers=headers,
    )
    assert r4.status_code == 400
    js4 = r4.json() or {}
    assert (
        str(js4.get("detail") or "").startswith("required_attribute_missing")
        or str((js4.get("error") or {}).get("code") or "").startswith("required_attribute_missing")
    )

    # Update item with invalid type
    item_id = int(item.get("id") or 0)
    assert item_id > 0

    r5 = client.patch(
        f"/admin/catalog/items/{item_id}",
        json={"attributes": {"price": "oops"}},
        headers=headers,
    )
    assert r5.status_code == 400
    js5 = r5.json() or {}
    assert (
        str(js5.get("detail") or "").startswith("invalid_attribute_type")
        or str((js5.get("error") or {}).get("code") or "").startswith("invalid_attribute_type")
    )

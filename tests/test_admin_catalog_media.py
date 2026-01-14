from __future__ import annotations


def test_admin_catalog_media_crud_and_reorder(client):
    headers = {"X-Tenant-Id": "1"}

    # Create item type
    r1 = client.post(
        "/admin/catalog/item-types",
        json={
            "key": "product_media",
            "name": "Produtos com Mídia",
            "schema": {
                "fields": [
                    {"key": "price", "label": "Preço", "type": "number", "required": False},
                ]
            },
            "is_active": True,
        },
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    # Create item
    r2 = client.post(
        "/admin/catalog/items",
        json={
            "item_type_key": "product_media",
            "title": "Item 1",
            "description": "Desc",
            "attributes": {"price": 10},
            "is_active": True,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    item = r2.json()
    item_id = int(item.get("id") or 0)
    assert item_id > 0

    # Add media
    r3 = client.post(
        f"/admin/catalog/items/{item_id}/media",
        json={"kind": "image", "url": "https://example.com/a.jpg"},
        headers=headers,
    )
    assert r3.status_code == 200, r3.text
    m1 = r3.json()

    r4 = client.post(
        f"/admin/catalog/items/{item_id}/media",
        json={"kind": "image", "url": "https://example.com/b.jpg"},
        headers=headers,
    )
    assert r4.status_code == 200, r4.text
    m2 = r4.json()

    # List media
    r5 = client.get(f"/admin/catalog/items/{item_id}/media", headers=headers)
    assert r5.status_code == 200, r5.text
    media = r5.json()
    assert len(media) == 2
    assert media[0]["url"] == "https://example.com/a.jpg"
    assert media[1]["url"] == "https://example.com/b.jpg"

    # Reorder (swap)
    r6 = client.post(
        f"/admin/catalog/items/{item_id}/media/reorder",
        json={"media_ids": [int(m2["id"]), int(m1["id"])]},
        headers=headers,
    )
    assert r6.status_code == 200, r6.text

    r7 = client.get(f"/admin/catalog/items/{item_id}/media", headers=headers)
    assert r7.status_code == 200
    media2 = r7.json()
    assert media2[0]["id"] == int(m2["id"])
    assert media2[1]["id"] == int(m1["id"])

    # Delete one
    r8 = client.delete(f"/admin/catalog/media/{int(m1['id'])}", headers=headers)
    assert r8.status_code == 200, r8.text

    r9 = client.get(f"/admin/catalog/items/{item_id}/media", headers=headers)
    assert r9.status_code == 200
    media3 = r9.json()
    assert len(media3) == 1
    assert media3[0]["id"] == int(m2["id"])

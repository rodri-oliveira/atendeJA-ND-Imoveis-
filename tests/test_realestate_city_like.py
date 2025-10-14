def _create_property(client, title: str, city: str, state: str = "SP") -> int:
    body = {
        "titulo": title,
        "tipo": "apartment",
        "finalidade": "sale",
        "preco": 100000.0,
        "cidade": city,
        "estado": state,
        "descricao": "Teste filtro cidade ilike",
    }
    r = client.post("/re/imoveis", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_city_filter_ilike_substring(client):
    # Arrange: duas cidades contendo o substring "Alpha"
    _create_property(client, "Imovel AlphaVille", "AlphaVille")
    _create_property(client, "Imovel VilleAlpha", "VilleAlpha")

    # Act: filtro por substring
    r = client.get("/re/imoveis?cidade=Alpha&limit=50")
    assert r.status_code == 200, r.text
    hdr = r.headers.get("X-Total-Count")
    data = r.json()

    # Assert: ambas devem ser retornadas
    assert hdr is not None and hdr.isdigit()
    assert int(hdr) == 2
    assert isinstance(data, list) and len(data) == 2
def _create_property(client, title: str, city: str, state: str = "SP") -> int:
    body = {
        "titulo": title,
        "tipo": "apartment",
        "finalidade": "sale",
        "preco": 100000.0,
        "cidade": city,
        "estado": state,
        "descricao": "Teste de listagem",
    }
    r = client.post("/re/imoveis", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _add_image(client, prop_id: int, url: str):
    payload = {
        "url": url,
        "is_capa": True,
        "ordem": 0,
    }
    r = client.post(f"/re/imoveis/{prop_id}/imagens", json=payload)
    assert r.status_code == 200, r.text


def test_list_sets_x_total_count_and_paginates_with_filters(client):
    # Arrange: dois imóveis na mesma cidade exclusiva
    city = "ZetaCityGroup"
    _create_property(client, "Imovel Zeta 1", city)
    _create_property(client, "Imovel Zeta 2", city)

    # Act: listar com limit=1 e filtro por cidade
    r = client.get(f"/re/imoveis?cidade={city}&limit=1&offset=0")
    assert r.status_code == 200, r.text
    hdr = r.headers.get("X-Total-Count")
    data = r.json()

    # Assert
    assert hdr is not None, "X-Total-Count deve estar presente"
    assert hdr.isdigit(), "X-Total-Count deve ser numérico"
    assert int(hdr) == 2, "Total filtrado deve refletir 2 imóveis"
    assert isinstance(data, list) and len(data) == 1, "limit deve aplicar na paginação"


def test_list_only_with_cover_filters_correctly(client):
    # Arrange: dois imóveis em cidade exclusiva; apenas um com imagem
    city = "ZetaCityCover"
    p1 = _create_property(client, "Imovel Cover 1", city)
    _create_property(client, "Imovel Cover 2", city)
    _add_image(
        client,
        p1,
        "https://imgs2.cdn-imobibrasil.com.br/imagens/imoveis/202106251237157000.png",
    )

    # Act: listar somente com capa
    r = client.get(f"/re/imoveis?cidade={city}&only_with_cover=true&limit=50")
    assert r.status_code == 200, r.text
    hdr = r.headers.get("X-Total-Count")
    data = r.json()

    # Assert
    assert hdr is not None and hdr.isdigit()
    assert int(hdr) == 1, "Apenas o imóvel com imagem deve ser contado"
    assert isinstance(data, list) and len(data) == 1
import io
import os
from app.core.config import settings


def skip_if_read_only():
    if getattr(settings, "RE_READ_ONLY", False):
        import pytest
        pytest.skip("RE_READ_ONLY habilitado, pulando testes que escrevem no banco")


def test_import_csv_happy_path(client):
    skip_if_read_only()
    csv_content = (
        "titulo,descricao,tipo,finalidade,preco,condominio,iptu,cidade,estado,bairro,dormitorios,banheiros,suites,vagas,area_total,area_util,ano_construcao,external_id,source,updated_at_source,imagens_urls\n"
        "Apto Teste,Andar alto,apartment,rent,3000,550,120,São Paulo,SP,Centro,2,1,0,1,65,60,2012,EXT-TEST-001,pytest,2025-01-01T00:00:00Z,https://cdn/1.jpg;https://cdn/2.jpg\n"
    ).encode("utf-8")
    files = {"file": ("import.csv", io.BytesIO(csv_content), "text/csv")}
    resp = client.post("/admin/re/imoveis/import-csv", files=files, headers={"X-Tenant-Id": "1"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(["created", "updated", "images_created"]).issubset(data.keys())

    # Reimport para forçar update (idempotência por external_id)
    resp2 = client.post("/admin/re/imoveis/import-csv", files=files, headers={"X-Tenant-Id": "1"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["updated"] >= 0


def test_import_csv_missing_column_returns_400(client):
    skip_if_read_only()
    # Removemos 'tipo' do header para simular falta de coluna obrigatória
    csv_bad = (
        "titulo,descricao,finalidade,preco,condominio,iptu,cidade,estado,bairro,dormitorios,banheiros,suites,vagas,area_total,area_util,ano_construcao,external_id,source,updated_at_source,imagens_urls\n"
        "Apto Teste,Andar alto,rent,3000,550,120,São Paulo,SP,Centro,2,1,0,1,65,60,2012,EXT-TEST-002,pytest,2025-01-01T00:00:00Z,https://cdn/1.jpg\n"
    ).encode("utf-8")
    files = {"file": ("import.csv", io.BytesIO(csv_bad), "text/csv")}
    resp = client.post("/admin/re/imoveis/import-csv", files=files, headers={"X-Tenant-Id": "1"})
    assert resp.status_code == 400, resp.text
    payload = resp.json()
    # Handler global envelopa como {"error": {"code": ..., "message": ...}}
    assert payload.get("error", {}).get("code") in {"missing_columns", "bad_request"}


def test_get_imovel_detalhes_roundtrip(client):
    # Cria um imóvel mínimo via API e lê os detalhes
    body = {
        "titulo": "Imóvel para teste",
        "tipo": "apartment",
        "finalidade": "sale",
        "preco": 123456.78,
        "cidade": "São Paulo",
        "estado": "SP",
        "descricao": "Teste automatizado",
    }
    r = client.post("/re/imoveis", json=body)
    assert r.status_code in (200, 201), r.text
    imovel = r.json()
    prop_id = imovel["id"]

    r2 = client.get(f"/re/imoveis/{prop_id}/detalhes")
    assert r2.status_code == 200, r2.text
    det = r2.json()
    for k in ["id", "titulo", "tipo", "finalidade", "preco", "cidade", "estado", "imagens"]:
        assert k in det

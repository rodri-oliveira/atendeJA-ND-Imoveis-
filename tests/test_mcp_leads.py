from fastapi.testclient import TestClient
from app.main import app
from app.repositories.db import SessionLocal
from app.domain.realestate.models import Lead


client = TestClient(app)


def test_mcp_criar_lead_basic():
    body = {
        "input": "",
        "mode": "tool",
        "tool": "criar_lead",
        "params": {
            "nome": "Fulano",
            "telefone": "+5511999990000",
            "email": "fulano@exemplo.com",
            "origem": "mcp",
            "preferencias": {"finalidade": "sale", "cidade": "São Paulo"},
            "consentimento_lgpd": True,
        },
    }
    r = client.post("/mcp/execute", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "tool_executed"
    tcalls = data.get("tool_calls", [])
    assert tcalls and tcalls[0]["tool"] == "criar_lead"
    res = tcalls[0]["result"]
    assert isinstance(res.get("id"), int)
    assert res.get("telefone") == "+5511999990000"


def test_mcp_criar_lead_with_property_and_campaign():
    # Arrange: cria um imóvel mínimo via API para usar como property_interest_id
    prop_body = {
        "titulo": "Imóvel MCP Teste",
        "tipo": "apartment",
        "finalidade": "sale",
        "preco": 250000.0,
        "cidade": "São Paulo",
        "estado": "SP",
        "descricao": "Teste MCP",
    }
    r_prop = client.post("/re/imoveis", json=prop_body)
    assert r_prop.status_code in (200, 201), r_prop.text
    prop_id = r_prop.json()["id"]

    body = {
        "input": "",
        "mode": "tool",
        "tool": "criar_lead",
        "params": {
            "nome": "Beltrano",
            "telefone": "+5511999991111",
            "email": "beltrano@exemplo.com",
            "origem": "mcp",
            "consentimento_lgpd": True,
            # Direcionamento/integração
            "property_interest_id": prop_id,
            "external_property_id": "EXT-XYZ",
            # Filtros e campanha
            "finalidade": "sale",
            "tipo": "apartment",
            "cidade": "São Paulo",
            "estado": "SP",
            "dormitorios": 2,
            "preco_max": 400000,
            "campaign_source": "chavesnamao",
            "campaign_medium": "cpc",
            "campaign_name": "campanha_teste",
        },
    }
    r = client.post("/mcp/execute", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["message"] == "tool_executed"
    tcalls = data.get("tool_calls", [])
    assert tcalls and tcalls[0]["tool"] == "criar_lead"
    res = tcalls[0]["result"]
    lead_id = res.get("id")
    assert isinstance(lead_id, int)

    # Verifica no banco que os campos foram persistidos
    with SessionLocal() as db:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        assert lead is not None
        assert lead.phone == "+5511999991111"
        assert lead.property_interest_id == prop_id
        assert lead.external_property_id == "EXT-XYZ"
        assert lead.finalidade == "sale"
        assert lead.tipo == "apartment"
        assert lead.cidade == "São Paulo"
        assert (lead.estado or "").upper() == "SP"
        assert lead.dormitorios == 2
        assert lead.preco_max == 400000
        assert lead.campaign_source == "chavesnamao"
        assert lead.campaign_medium == "cpc"
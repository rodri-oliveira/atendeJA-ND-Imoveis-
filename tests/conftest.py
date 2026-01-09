import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Garantir ambiente de testes previsível
os.environ["APP_ENV"] = "test"
os.environ["WA_PROVIDER"] = "noop"
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite:///:memory:")
os.environ.setdefault("DEFAULT_TENANT_ID", "1")

# Ensure the project root (which contains the 'app' package) is on sys.path
THIS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.main import app
from app.api.deps import get_db as deps_get_db
from app.repositories.db import Base
from app.repositories.models import Tenant


@pytest.fixture(scope="function")
def db_session():
    """Cria uma sessão de banco de dados em memória para cada função de teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        if db.get(Tenant, 1) is None:
            db.add(Tenant(id=1, name="tenant-1"))
            db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Cria um TestClient que usa a sessão de banco de dados do teste."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Sobrescreve a dependência de DB definida em app.main e na rota de imóveis
    app.dependency_overrides[deps_get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# Fixtures específicas para testes das melhorias do LLM
@pytest.fixture
def sample_llm_entities():
    """Fixture com entidades de exemplo para testes."""
    return {
        "finalidade": "rent",
        "tipo": "apartment",
        "cidade": "São Paulo",
        "dormitorios": 2,
        "preco_max": 3000,
        "preco_min": 1500
    }

@pytest.fixture
def sample_conversation_state():
    """Fixture com estado de conversa de exemplo."""
    return {
        "stage": "awaiting_purpose",
        "tenant_id": "test_tenant",
        "contact_id": "test_contact",
        "conversation_id": "test_conversation",
        "filters": {},
        "retry_count": 0,
        "user_name": None,
        "lgpd_consent": None
    }

@pytest.fixture
def simple_responses():
    """Fixture com respostas simples que não devem ter entidades."""
    return ["sim", "não", "ok", "ola", "oi", "obrigado", "tchau"]

@pytest.fixture
def valid_search_inputs():
    """Fixture com entradas válidas de busca de imóvel."""
    return [
        "quero alugar apartamento 2 quartos em São Paulo",
        "busco casa para comprar em Campinas",
        "apartamento 3 dormitórios para alugar",
        "casa até 500 mil reais"
    ]

@pytest.fixture
def hallucination_scenarios():
    """Fixture com cenários de alucinação do LLM."""
    return [
        {
            "input": "sim",
            "llm_output": {
                "intent": "responder_lgpd",
                "entities": {
                    "finalidade": "rent",
                    "tipo": "apartment",
                    "cidade": "São Paulo"
                }
            },
            "expected_entities": {
                "finalidade": None,
                "tipo": None,
                "cidade": None
            }
        },
        {
            "input": "ola",
            "llm_output": {
                "intent": "outro",
                "entities": {
                    "dormitorios": 3,
                    "preco_max": 400000
                }
            },
            "expected_entities": {
                "dormitorios": None,
                "preco_max": None
            }
        }
    ]

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

# Ensure the project root (which contains the 'app' package) is on sys.path
THIS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.main import app
from app.api.deps import get_db as deps_get_db
from app.repositories.db import Base


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
    del app.dependency_overrides[deps_get_db]

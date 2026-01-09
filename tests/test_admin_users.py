from fastapi.testclient import TestClient

from app.main import app
from app.repositories.db import engine, SessionLocal
from app.repositories.models import Base, User, UserRole, Tenant
from app.core.security import get_password_hash

client = TestClient(app)


def setup_module(module):
    # Como APP_ENV=test não cria tabelas no startup, garantimos aqui
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(Tenant, 1) is None:
            db.add(Tenant(id=1, name="tenant-1"))
            db.commit()


def _ensure_admin(email: str = "admin@test.local", password: str = "pass123"):
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == email).first()
        if not admin:
            admin = User(
                email=email,
                full_name="Admin Test",
                hashed_password=get_password_hash(password),
                is_active=True,
                role=UserRole.admin,
                tenant_id=1,
            )
            db.add(admin)
            db.commit()
        return email, password


def _login(email: str, password: str) -> str:
    resp = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_admin_user_crud_flow():
    # Arrange: admin
    email, password = _ensure_admin()
    token = _login(email, password)
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": "1"}

    # Create collaborator
    create_payload = {
        "email": "colab1@test.local",
        "password": "secret",
        "full_name": "Colaborador 1",
        "role": "collaborator",
        "is_active": True,
    }
    r = client.post("/admin/users", json=create_payload, headers=headers)
    assert r.status_code == 200, r.text
    user = r.json()
    user_id = user["id"]
    assert user["email"] == create_payload["email"]
    assert user["role"] == "collaborator"
    assert user["is_active"] is True

    # List
    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 200, r.text
    lst = r.json()
    assert any(u["email"] == create_payload["email"] for u in lst)

    # Update (promote to admin and deactivate)
    patch_payload = {"role": "admin", "is_active": False}
    r = client.patch(f"/admin/users/{user_id}", json=patch_payload, headers=headers)
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["role"] == "admin"
    assert up["is_active"] is False

    # Login as collaborator should fail now (inactive)
    r = client.post(
        "/auth/login",
        data={
            "username": create_payload["email"],
            "password": create_payload["password"],
        },
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 400

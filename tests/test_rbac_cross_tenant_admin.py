from __future__ import annotations

from app.core.security import create_access_token
from app.repositories.models import Tenant, User, UserRole


def test_admin_cannot_access_other_tenant_via_x_tenant_header(client, db_session):
    if db_session.get(Tenant, 1) is None:
        db_session.add(Tenant(id=1, name="tenant-1"))
    if db_session.get(Tenant, 2) is None:
        db_session.add(Tenant(id=2, name="tenant-2"))
    db_session.commit()

    user = User(
        email="admin1@example.com",
        full_name="Admin 1",
        hashed_password="x",
        is_active=True,
        role=UserRole.admin,
        tenant_id=1,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.email, extra={"role": user.role.value, "tenant_id": user.tenant_id})

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "2",
    }
    r = client.get("/admin/re/chatbot-flows", headers=headers)

    assert r.status_code == 403, r.text
    body = r.json() or {}
    assert (body.get("error") or {}).get("code") == "cross_tenant_forbidden"

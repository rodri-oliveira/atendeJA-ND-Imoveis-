from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_user
from app.core.config import settings
from app.repositories.models import Tenant, User
from app.services.tenant_resolver import resolve_chatbot_domain_for_tenant


router = APIRouter()


class TenantDomainOut(BaseModel):
    domain: str


class TenantInfoOut(BaseModel):
    tenant_id: int
    tenant_name: str | None = None


@router.get("/domain", response_model=TenantDomainOut)
def get_tenant_domain(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    expected = (settings.SUPER_ADMIN_API_KEY or "").strip()
    if not expected:
        env = (settings.APP_ENV or "").lower()
        if env in {"dev", "test"}:
            expected = "dev"

    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0) if current_user else 0
    if expected and (x_super_admin_key or "").strip() == expected:
        if not x_tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_tenant_id")
        try:
            tenant_id = int(str(x_tenant_id).strip())
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_tenant_id")
    elif current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    domain = resolve_chatbot_domain_for_tenant(db=db, tenant_id=tenant_id) if tenant_id else "real_estate"
    return TenantDomainOut(domain=domain)


@router.get("/tenant", response_model=TenantInfoOut)
def get_active_tenant_info(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    expected = (settings.SUPER_ADMIN_API_KEY or "").strip()
    if not expected:
        env = (settings.APP_ENV or "").lower()
        if env in {"dev", "test"}:
            expected = "dev"

    tenant_id = 0
    if expected and (x_super_admin_key or "").strip() == expected:
        if not x_tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_tenant_id")
        try:
            tenant_id = int(str(x_tenant_id).strip())
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_tenant_id")
    elif current_user is not None:
        tenant_id = int(getattr(current_user, "tenant_id", 0) or 0)
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    tenant_name: str | None = None
    if tenant_id:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant:
            tenant_name = str(getattr(tenant, "name", "") or "") or None

    return TenantInfoOut(tenant_id=int(tenant_id), tenant_name=tenant_name)

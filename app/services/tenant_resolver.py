from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories import models as core_models


@dataclass(frozen=True)
class TenantResolutionError(Exception):
    status_code: int
    detail: str


def resolve_tenant_id_from_input(tenant_id_value: object) -> int:
    try:
        return int(str(tenant_id_value).strip())
    except Exception:
        try:
            return int(str(settings.DEFAULT_TENANT_ID).strip())
        except Exception:
            return 1


def resolve_tenant_from_phone_number_id(db: Session, phone_number_id: str | None) -> core_models.Tenant:
    pnid = (phone_number_id or "").strip()
    if not pnid:
        raise TenantResolutionError(status_code=400, detail="missing_phone_number_id")

    acct = (
        db.query(core_models.WhatsAppAccount)
        .filter(
            core_models.WhatsAppAccount.phone_number_id == pnid,
            core_models.WhatsAppAccount.is_active == True,  # noqa: E712
        )
        .order_by(core_models.WhatsAppAccount.id.desc())
        .first()
    )
    if not acct:
        raise TenantResolutionError(status_code=404, detail="tenant_not_mapped_for_phone_number_id")

    tenant = db.get(core_models.Tenant, int(acct.tenant_id))
    if not tenant:
        raise TenantResolutionError(status_code=404, detail="tenant_not_found_for_whatsapp_account")

    if not bool(getattr(tenant, "is_active", True)):
        raise TenantResolutionError(status_code=403, detail="tenant_suspended")

    return tenant

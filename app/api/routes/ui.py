from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_user
from app.core.config import settings
from app.repositories.models import Tenant, User, UserRole
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.domain.chatbot.flow_templates import list_available_templates
from app.services.tenant_resolver import resolve_chatbot_domain_for_tenant


router = APIRouter()


class TenantDomainOut(BaseModel):
    domain: str


class TenantInfoOut(BaseModel):
    tenant_id: int
    tenant_name: str | None = None


class SupportedDomainOut(BaseModel):
    domains: list[str]


class DomainFlowStatusOut(BaseModel):
    domain: str
    has_published_flow: bool
    has_lead_kanban: bool
    has_lead_summary: bool


class TenantDomainsOut(BaseModel):
    tenant_id: int
    tenant_name: str | None = None
    active_domain: str
    enabled_domains: list[str]
    by_domain: list[DomainFlowStatusOut]


class TenantEnabledDomainsIn(BaseModel):
    enabled_domains: list[str]


class TenantActiveDomainIn(BaseModel):
    active_domain: str


def _resolve_super_admin_key_expected() -> str:
    expected = (settings.SUPER_ADMIN_API_KEY or "").strip()
    if not expected:
        env = (settings.APP_ENV or "").lower()
        if env in {"dev", "test"}:
            expected = "dev"
    return expected


def _resolve_tenant_id_for_ui(
    *,
    current_user: User | None,
    x_tenant_id: str | None,
    x_super_admin_key: str | None,
) -> int:
    expected = _resolve_super_admin_key_expected()

    tenant_id = int(getattr(current_user, "tenant_id", 0) or 0) if current_user else 0
    if expected and (x_super_admin_key or "").strip() == expected:
        if not x_tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_tenant_id")
        try:
            return int(str(x_tenant_id).strip())
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_tenant_id")

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_assigned_to_tenant")
    return int(tenant_id)


def _require_admin_or_super_admin(
    *,
    current_user: User | None,
    x_super_admin_key: str | None,
    x_tenant_id: str | None,
) -> None:
    expected = _resolve_super_admin_key_expected()
    if expected and (x_super_admin_key or "").strip() == expected:
        if not x_tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_tenant_id")
        return
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    if getattr(current_user, "role", None) != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_only")


@router.get("/domain", response_model=TenantDomainOut)
def get_tenant_domain(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    tenant_id = _resolve_tenant_id_for_ui(current_user=current_user, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)
    domain = resolve_chatbot_domain_for_tenant(db=db, tenant_id=tenant_id) if tenant_id else "real_estate"
    return TenantDomainOut(domain=domain)


@router.get("/tenant", response_model=TenantInfoOut)
def get_active_tenant_info(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    tenant_id = _resolve_tenant_id_for_ui(current_user=current_user, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)

    tenant_name: str | None = None
    if tenant_id:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant:
            tenant_name = str(getattr(tenant, "name", "") or "") or None

    return TenantInfoOut(tenant_id=int(tenant_id), tenant_name=tenant_name)


@router.get("/domains", response_model=SupportedDomainOut)
def list_supported_domains():
    domains = sorted({str(t.get("domain") or "").strip() for t in (list_available_templates() or []) if str(t.get("domain") or "").strip()})
    if not domains:
        domains = ["real_estate"]
    return SupportedDomainOut(domains=domains)


@router.get("/tenant/domains", response_model=TenantDomainsOut)
def get_tenant_domains(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    tenant_id = _resolve_tenant_id_for_ui(current_user=current_user, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")

    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    active_domain = (settings_json.get("chatbot_domain") or "").strip() or "real_estate"
    raw_enabled = settings_json.get("enabled_domains")
    if isinstance(raw_enabled, list):
        enabled_domains = [str(x).strip() for x in raw_enabled if str(x).strip()]
    else:
        enabled_domains = []

    if not enabled_domains:
        enabled_domains = [active_domain]
    if active_domain not in enabled_domains:
        enabled_domains = [active_domain, *[d for d in enabled_domains if d != active_domain]]

    supported = list_supported_domains().domains
    enabled_domains = [d for d in enabled_domains if d in supported] or [active_domain]

    flow_svc = ChatbotFlowService(db)
    by_domain: list[DomainFlowStatusOut] = []
    for d in enabled_domains:
        row = flow_svc.get_published_flow(tenant_id=int(tenant_id), domain=d)
        has_kanban = False
        has_summary = False
        if row and isinstance(getattr(row, "flow_definition", None), dict):
            try:
                flow = flow_svc.validate_definition(row.flow_definition)
                has_kanban = bool(getattr(flow, "lead_kanban", None) and getattr(flow.lead_kanban, "stages", None))
                has_summary = bool(getattr(flow, "lead_summary", None) and getattr(flow.lead_summary, "fields", None))
            except Exception:
                has_kanban = False
                has_summary = False
        by_domain.append(
            DomainFlowStatusOut(
                domain=d,
                has_published_flow=bool(row),
                has_lead_kanban=has_kanban,
                has_lead_summary=has_summary,
            )
        )

    return TenantDomainsOut(
        tenant_id=int(tenant_id),
        tenant_name=str(getattr(tenant, "name", "") or "") or None,
        active_domain=active_domain,
        enabled_domains=enabled_domains,
        by_domain=by_domain,
    )


@router.put("/tenant/enabled-domains", response_model=TenantDomainsOut)
def update_tenant_enabled_domains(
    payload: TenantEnabledDomainsIn,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    _require_admin_or_super_admin(current_user=current_user, x_super_admin_key=x_super_admin_key, x_tenant_id=x_tenant_id)
    tenant_id = _resolve_tenant_id_for_ui(current_user=current_user, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")

    supported = list_supported_domains().domains
    proposed = [str(x).strip() for x in (payload.enabled_domains or []) if str(x).strip()]
    proposed = [d for d in proposed if d in supported]

    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    active_domain = (settings_json.get("chatbot_domain") or "").strip() or "real_estate"
    if not proposed:
        proposed = [active_domain]
    if active_domain not in proposed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="active_domain_must_be_enabled")

    settings_json["enabled_domains"] = proposed
    tenant.settings_json = settings_json
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return get_tenant_domains(current_user=current_user, db=db, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)


@router.put("/tenant/active-domain", response_model=TenantDomainsOut)
def update_tenant_active_domain(
    payload: TenantActiveDomainIn,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_super_admin_key: str | None = Header(default=None, alias="X-Super-Admin-Key"),
):
    _require_admin_or_super_admin(current_user=current_user, x_super_admin_key=x_super_admin_key, x_tenant_id=x_tenant_id)
    tenant_id = _resolve_tenant_id_for_ui(current_user=current_user, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")

    target = (payload.active_domain or "").strip()
    if not target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="active_domain_required")

    supported = list_supported_domains().domains
    if target not in supported:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_domain")

    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    raw_enabled = settings_json.get("enabled_domains")
    if isinstance(raw_enabled, list):
        enabled_domains = [str(x).strip() for x in raw_enabled if str(x).strip()]
    else:
        enabled_domains = []
    if not enabled_domains:
        enabled_domains = [target]
    if target not in enabled_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="active_domain_must_be_enabled")

    settings_json["chatbot_domain"] = target
    tenant.settings_json = settings_json
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return get_tenant_domains(current_user=current_user, db=db, x_tenant_id=x_tenant_id, x_super_admin_key=x_super_admin_key)

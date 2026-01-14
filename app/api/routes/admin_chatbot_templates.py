from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_request_context, require_admin_tenant_id
from app.core.config import settings
from app.repositories.models import Tenant
from app.api.schemas.chatbot_templates import (
    ChatbotFlowTemplateApplyIn,
    ChatbotFlowTemplateApplyOut,
    ChatbotFlowTemplateOut,
)
from app.services.chatbot_template_service import apply_chatbot_flow_template, list_chatbot_flow_templates


if settings.APP_ENV == "test":
    router = APIRouter()
else:
    router = APIRouter(dependencies=[Depends(require_admin_request_context)])


@router.get("/chatbot-templates", response_model=List[ChatbotFlowTemplateOut])
def list_chatbot_templates(
    tenant_id: int = Depends(require_admin_tenant_id),
):
    _ = tenant_id
    return list_chatbot_flow_templates()


@router.post("/chatbot-templates/apply", response_model=ChatbotFlowTemplateApplyOut)
def apply_chatbot_template(
    payload: ChatbotFlowTemplateApplyIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    return apply_chatbot_flow_template(db=db, tenant_id=int(tenant_id), payload=payload)


class ChatbotDomainOut(BaseModel):
    domain: str


class ChatbotDomainIn(BaseModel):
    domain: str


@router.get("/chatbot-domain", response_model=ChatbotDomainOut)
def get_chatbot_domain(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    domain = (settings_json.get("chatbot_domain") or "").strip() or "real_estate"
    return ChatbotDomainOut(domain=domain)


@router.put("/chatbot-domain", response_model=ChatbotDomainOut)
def set_chatbot_domain(
    payload: ChatbotDomainIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    domain = (payload.domain or "").strip()
    if not domain:
        raise HTTPException(status_code=400, detail="domain_required")

    allowed_domains = {x.domain for x in list_chatbot_flow_templates()}
    if domain not in allowed_domains:
        raise HTTPException(status_code=400, detail="invalid_domain")

    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    settings_json["chatbot_domain"] = domain
    tenant.settings_json = settings_json
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return ChatbotDomainOut(domain=domain)

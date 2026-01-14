from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.schemas.chatbot_templates import (
    ChatbotFlowTemplateApplyIn,
    ChatbotFlowTemplateApplyOut,
    ChatbotFlowTemplateOut,
)
from app.domain.chatbot.flow_templates import get_flow_template_definition, list_available_templates
from app.domain.realestate import models as re_models
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService


def list_chatbot_flow_templates() -> List[ChatbotFlowTemplateOut]:
    return [ChatbotFlowTemplateOut(**x) for x in list_available_templates()]


def apply_chatbot_flow_template(
    *,
    db: Session,
    tenant_id: int,
    payload: ChatbotFlowTemplateApplyIn,
    commit: bool = True,
) -> ChatbotFlowTemplateApplyOut:
    domain = (payload.domain or "").strip()
    if not domain:
        raise HTTPException(status_code=400, detail="domain_required")

    template = (payload.template or "").strip()
    if not template:
        raise HTTPException(status_code=400, detail="template_required")

    name = (payload.name or "default").strip() or "default"

    try:
        flow_definition = get_flow_template_definition(domain=domain, template=template)
    except ValueError as e:
        if str(e) == "template_not_found":
            raise HTTPException(status_code=404, detail="template_not_found")
        raise

    svc = ChatbotFlowService(db)
    svc.validate_definition(flow_definition)

    row = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == domain,
            re_models.ChatbotFlow.name == name,
        )
        .first()
    )

    if not row:
        row = re_models.ChatbotFlow(
            tenant_id=int(tenant_id),
            domain=domain,
            name=name,
            flow_definition=flow_definition,
            is_published=False,
            published_version=0,
        )
        db.add(row)
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()
    else:
        if payload.overwrite:
            row.flow_definition = flow_definition
            db.add(row)
            if commit:
                db.commit()
                db.refresh(row)
            else:
                db.flush()

    if not payload.publish:
        return ChatbotFlowTemplateApplyOut(ok=True, flow_id=int(row.id), published=bool(row.is_published))

    current_max = (
        db.query(func.max(re_models.ChatbotFlow.published_version))
        .filter(re_models.ChatbotFlow.tenant_id == int(tenant_id), re_models.ChatbotFlow.domain == domain)
        .scalar()
    )
    next_version = int(current_max or 0) + 1

    db.query(re_models.ChatbotFlow).filter(
        re_models.ChatbotFlow.tenant_id == int(tenant_id),
        re_models.ChatbotFlow.domain == domain,
    ).update({re_models.ChatbotFlow.is_published: False})

    row.is_published = True
    row.published_version = next_version
    row.published_at = datetime.utcnow()
    row.published_by = "admin-template"
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    return ChatbotFlowTemplateApplyOut(
        ok=True,
        flow_id=int(row.id),
        published=True,
        published_version=int(row.published_version or 0),
    )

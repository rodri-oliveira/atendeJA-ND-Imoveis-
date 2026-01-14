from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_request_context, require_admin_tenant_id
from app.core.config import settings
from app.domain.realestate import models as re_models
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.domain.chatbot.flow_templates import get_flow_template_definition
from app.services.conversation_context import normalize_state
from app.services.flow_engine import FlowEngine


if settings.APP_ENV == "test":
    router = APIRouter()
else:
    router = APIRouter(dependencies=[Depends(require_admin_request_context)])


class ChatbotFlowOut(BaseModel):
    id: int
    tenant_id: int
    domain: str
    name: str
    is_published: bool
    is_archived: bool
    published_version: int
    published_at: Optional[str] = None
    published_by: Optional[str] = None
    archived_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatbotFlowDetailOut(ChatbotFlowOut):
    flow_definition: Dict[str, Any]


class ChatbotFlowUpsertIn(BaseModel):
    domain: str
    name: str
    flow_definition: Dict[str, Any]


class ChatbotFlowPublishOut(BaseModel):
    ok: bool = True
    published_flow_id: int
    published_version: int


class ChatbotFlowPublishedCurrentOut(BaseModel):
    published: bool
    flow: ChatbotFlowOut | None = None


class ChatbotFlowPublishByVersionIn(BaseModel):
    domain: str
    published_version: int


class ChatbotFlowPreviewIn(BaseModel):
    sender_id: str = "preview"
    input: str
    state: Optional[Dict[str, Any]] = None


class ChatbotFlowPreviewOut(BaseModel):
    message: str
    state: Dict[str, Any]
    handled: bool
    continue_loop: bool


class ChatbotFlowCreateFromTemplateIn(BaseModel):
    domain: str
    template: str = "default"
    name: str = "default"
    overwrite: bool = False
    publish: bool = True


class ChatbotFlowCreateFromTemplateOut(BaseModel):
    ok: bool = True
    flow_id: int
    published: bool
    published_version: int | None = None


class ChatbotFlowCloneIn(BaseModel):
    name: str
    overwrite: bool = False
    publish: bool = False


class ChatbotFlowCloneOut(BaseModel):
    ok: bool = True
    source_flow_id: int
    new_flow_id: int
    published: bool
    published_version: int | None = None


class ChatbotFlowDeleteOut(BaseModel):
    ok: bool = True
    deleted_flow_id: int


class ChatbotFlowArchiveOut(BaseModel):
    ok: bool = True
    flow_id: int
    is_archived: bool


def _flow_to_out(row: re_models.ChatbotFlow) -> ChatbotFlowOut:
    def _dt(v):
        try:
            return v.isoformat() if v else None
        except Exception:
            return None

    return ChatbotFlowOut(
        id=int(row.id),
        tenant_id=int(row.tenant_id),
        domain=str(row.domain),
        name=str(row.name),
        is_published=bool(row.is_published),
        is_archived=bool(getattr(row, "is_archived", False)),
        published_version=int(row.published_version or 0),
        published_at=_dt(getattr(row, "published_at", None)),
        published_by=(getattr(row, "published_by", None) or None),
        archived_at=_dt(getattr(row, "archived_at", None)),
        created_at=_dt(getattr(row, "created_at", None)),
        updated_at=_dt(getattr(row, "updated_at", None)),
    )


def _flow_to_detail_out(row: re_models.ChatbotFlow) -> ChatbotFlowDetailOut:
    base = _flow_to_out(row)
    return ChatbotFlowDetailOut(**base.model_dump(), flow_definition=dict(getattr(row, "flow_definition", {}) or {}))


@router.get("/chatbot-flows", response_model=List[ChatbotFlowOut])
def list_chatbot_flows(
    domain: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    q = db.query(re_models.ChatbotFlow).filter(re_models.ChatbotFlow.tenant_id == int(tenant_id))
    if domain:
        q = q.filter(re_models.ChatbotFlow.domain == str(domain))
    if not include_archived:
        q = q.filter(re_models.ChatbotFlow.is_archived == False)  # noqa: E712
    rows = q.order_by(re_models.ChatbotFlow.updated_at.desc(), re_models.ChatbotFlow.id.desc()).all()
    return [_flow_to_out(r) for r in rows]


@router.get("/chatbot-flows/by-key", response_model=ChatbotFlowDetailOut)
def get_chatbot_flow_by_key(
    domain: str,
    name: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    d = (domain or "").strip() or "real_estate"
    n = (name or "").strip()
    if not n:
        raise HTTPException(status_code=400, detail="name_required")

    row = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == d,
            re_models.ChatbotFlow.name == n,
        )
        .order_by(re_models.ChatbotFlow.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="flow_not_found")
    return _flow_to_detail_out(row)


@router.get("/chatbot-flows/by-id/{flow_id}", response_model=ChatbotFlowDetailOut)
def get_chatbot_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")
    return _flow_to_detail_out(row)


@router.post("/chatbot-flows", response_model=ChatbotFlowOut)
def upsert_chatbot_flow(
    payload: ChatbotFlowUpsertIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    domain = (payload.domain or "").strip() or "real_estate"
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")

    svc = ChatbotFlowService(db)
    svc.validate_definition(payload.flow_definition)

    existing = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == domain,
            re_models.ChatbotFlow.name == name,
        )
        .first()
    )

    if not existing:
        row = re_models.ChatbotFlow(
            tenant_id=int(tenant_id),
            domain=domain,
            name=name,
            flow_definition=payload.flow_definition,
            is_published=False,
            published_version=0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _flow_to_out(row)

    existing.flow_definition = payload.flow_definition
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return _flow_to_out(existing)


@router.post("/chatbot-flows/create-from-template", response_model=ChatbotFlowCreateFromTemplateOut)
def create_chatbot_flow_from_template(
    payload: ChatbotFlowCreateFromTemplateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    domain = (payload.domain or "").strip() or "real_estate"
    template = (payload.template or "default").strip() or "default"
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
        db.commit()
        db.refresh(row)
    else:
        if payload.overwrite:
            row.flow_definition = flow_definition
            db.add(row)
            db.commit()
            db.refresh(row)

    if not payload.publish:
        return ChatbotFlowCreateFromTemplateOut(
            ok=True,
            flow_id=int(row.id),
            published=bool(row.is_published),
            published_version=(int(row.published_version or 0) or None),
        )

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
    db.commit()
    db.refresh(row)

    return ChatbotFlowCreateFromTemplateOut(
        ok=True,
        flow_id=int(row.id),
        published=True,
        published_version=int(row.published_version or 0),
    )


@router.post("/chatbot-flows/{flow_id}/clone", response_model=ChatbotFlowCloneOut)
def clone_chatbot_flow(
    flow_id: int,
    payload: ChatbotFlowCloneIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    source = db.get(re_models.ChatbotFlow, int(flow_id))
    if not source or int(getattr(source, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    new_name = (payload.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="name_required")

    domain = str(getattr(source, "domain", "real_estate") or "real_estate")
    flow_definition = dict(getattr(source, "flow_definition", {}) or {})

    svc = ChatbotFlowService(db)
    svc.validate_definition(flow_definition)

    existing = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == domain,
            re_models.ChatbotFlow.name == new_name,
        )
        .first()
    )

    if existing:
        if not payload.overwrite:
            raise HTTPException(status_code=409, detail="flow_already_exists")
        existing.flow_definition = flow_definition
        db.add(existing)
        db.commit()
        db.refresh(existing)
        target = existing
    else:
        target = re_models.ChatbotFlow(
            tenant_id=int(tenant_id),
            domain=domain,
            name=new_name,
            flow_definition=flow_definition,
            is_published=False,
            published_version=0,
        )
        db.add(target)
        db.commit()
        db.refresh(target)

    if not payload.publish:
        return ChatbotFlowCloneOut(
            ok=True,
            source_flow_id=int(source.id),
            new_flow_id=int(target.id),
            published=bool(target.is_published),
            published_version=(int(target.published_version or 0) or None),
        )

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

    target.is_published = True
    target.published_version = next_version
    target.published_at = datetime.utcnow()
    target.published_by = "admin-clone"
    db.add(target)
    db.commit()
    db.refresh(target)

    return ChatbotFlowCloneOut(
        ok=True,
        source_flow_id=int(source.id),
        new_flow_id=int(target.id),
        published=True,
        published_version=int(target.published_version or 0),
    )


@router.delete("/chatbot-flows/{flow_id}", response_model=ChatbotFlowDeleteOut)
def delete_chatbot_flow(
    flow_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    if bool(getattr(row, "is_published", False)) and not bool(force):
        raise HTTPException(status_code=409, detail="cannot_delete_published_flow")

    db.delete(row)
    db.commit()
    return ChatbotFlowDeleteOut(ok=True, deleted_flow_id=int(flow_id))


@router.post("/chatbot-flows/{flow_id}/archive", response_model=ChatbotFlowArchiveOut)
def archive_chatbot_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    row.is_archived = True
    row.archived_at = datetime.utcnow()
    # Garantia extra: um flow arquivado não deve permanecer publicado
    if bool(getattr(row, "is_published", False)):
        row.is_published = False
    db.add(row)
    db.commit()
    db.refresh(row)
    return ChatbotFlowArchiveOut(ok=True, flow_id=int(row.id), is_archived=bool(row.is_archived))


@router.post("/chatbot-flows/{flow_id}/unarchive", response_model=ChatbotFlowArchiveOut)
def unarchive_chatbot_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    row.is_archived = False
    row.archived_at = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return ChatbotFlowArchiveOut(ok=True, flow_id=int(row.id), is_archived=bool(row.is_archived))


@router.post("/chatbot-flows/{flow_id}/publish", response_model=ChatbotFlowPublishOut)
def publish_chatbot_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    if bool(getattr(row, "is_archived", False)):
        raise HTTPException(status_code=409, detail="cannot_publish_archived_flow")

    svc = ChatbotFlowService(db)
    svc.validate_definition(row.flow_definition)

    current_max = (
        db.query(func.max(re_models.ChatbotFlow.published_version))
        .filter(re_models.ChatbotFlow.tenant_id == int(tenant_id), re_models.ChatbotFlow.domain == str(row.domain))
        .scalar()
    )
    next_version = int(current_max or 0) + 1

    db.query(re_models.ChatbotFlow).filter(
        re_models.ChatbotFlow.tenant_id == int(tenant_id),
        re_models.ChatbotFlow.domain == str(row.domain),
    ).update({re_models.ChatbotFlow.is_published: False})

    row.is_published = True
    row.published_version = next_version
    row.published_at = datetime.utcnow()
    row.published_by = "admin"
    db.add(row)
    db.commit()
    db.refresh(row)

    return ChatbotFlowPublishOut(published_flow_id=int(row.id), published_version=int(row.published_version or 0))


@router.get("/chatbot-flows/published", response_model=ChatbotFlowPublishedCurrentOut)
def get_published_chatbot_flow(
    domain: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == str(domain),
            re_models.ChatbotFlow.is_published == True,  # noqa: E712
            re_models.ChatbotFlow.is_archived == False,  # noqa: E712
        )
        .order_by(re_models.ChatbotFlow.published_version.desc(), re_models.ChatbotFlow.updated_at.desc())
        .first()
    )
    if not row:
        return ChatbotFlowPublishedCurrentOut(published=False, flow=None)
    return ChatbotFlowPublishedCurrentOut(published=True, flow=_flow_to_out(row))


@router.post("/chatbot-flows/publish-by-version", response_model=ChatbotFlowPublishOut)
def publish_chatbot_flow_by_version(
    payload: ChatbotFlowPublishByVersionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    domain = (payload.domain or "").strip() or "real_estate"
    target_version = int(payload.published_version)
    if target_version <= 0:
        raise HTTPException(status_code=400, detail="invalid_published_version")

    row = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == domain,
            re_models.ChatbotFlow.published_version == target_version,
        )
        .order_by(re_models.ChatbotFlow.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="flow_version_not_found")

    if bool(getattr(row, "is_archived", False)):
        raise HTTPException(status_code=409, detail="cannot_publish_archived_flow")

    svc = ChatbotFlowService(db)
    svc.validate_definition(row.flow_definition)

    db.query(re_models.ChatbotFlow).filter(
        re_models.ChatbotFlow.tenant_id == int(tenant_id),
        re_models.ChatbotFlow.domain == domain,
    ).update({re_models.ChatbotFlow.is_published: False})

    row.is_published = True
    row.published_at = datetime.utcnow()
    row.published_by = "admin"
    db.add(row)
    db.commit()
    db.refresh(row)

    return ChatbotFlowPublishOut(published_flow_id=int(row.id), published_version=int(row.published_version or 0))


@router.post("/chatbot-flows/{flow_id}/preview", response_model=ChatbotFlowPreviewOut)
def preview_chatbot_flow(
    flow_id: int,
    payload: ChatbotFlowPreviewIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    svc = ChatbotFlowService(db)
    flow = svc.validate_definition(row.flow_definition)

    sender_id = (payload.sender_id or "preview").strip() or "preview"
    loaded_state = payload.state or {}
    state = normalize_state(state=loaded_state, sender_id=sender_id, tenant_id=int(tenant_id), default_stage=str(flow.start or "start"))

    engine = FlowEngine(db)
    out = engine.try_process_message_with_definition(
        flow_definition=row.flow_definition,
        domain=(getattr(row, "domain", None) or "real_estate"),
        sender_id=sender_id,
        text_raw=(payload.input or ""),
        text_normalized=(payload.input or "").lower(),
        state=state,
    )

    return ChatbotFlowPreviewOut(
        message=out.message,
        state=out.state or state,
        handled=bool(out.handled),
        continue_loop=bool(out.continue_loop),
    )

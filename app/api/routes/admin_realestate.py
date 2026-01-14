from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Any, Dict

from app.api.deps import require_admin_request_context
from app.api.deps import require_admin_tenant_id
from app.api.deps import get_db

from sqlalchemy import select, func, delete
from app.domain.realestate import models as re_models
from app.domain.realestate.sources import ndimoveis as nd
from app.domain.realestate.importer import upsert_property
import httpx
import re
import time
from urllib.parse import urljoin
import contextlib
from sqlalchemy.orm import Session
from app.repositories.db import db_session
from app.domain.realestate.services.image_service import (
    delete_property_image,
    set_property_cover,
    reorder_property_images,
)
from app.domain.realestate.services.property_service import (
    set_active_property,
    soft_delete_property,
    hard_delete_property,
)
from app.messaging.provider import get_provider
from app.repositories.models import Tenant
from app.core.config import settings
from datetime import datetime
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.services.flow_engine import FlowEngine
from app.services.conversation_context import normalize_state
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

# Registro simples em memória para tarefas assíncronas (MVP)
TASKS: dict[str, dict] = {}

class ChatbotFlowOut(BaseModel):
    id: int
    tenant_id: int
    domain: str
    name: str
    is_published: bool
    published_version: int
    published_at: Optional[str] = None
    published_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ChatbotFlowUpsertIn(BaseModel):
    domain: str = "real_estate"
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
    domain: str = "real_estate"
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
        published_version=int(row.published_version or 0),
        published_at=_dt(getattr(row, "published_at", None)),
        published_by=(getattr(row, "published_by", None) or None),
        created_at=_dt(getattr(row, "created_at", None)),
        updated_at=_dt(getattr(row, "updated_at", None)),
    )

@router.get("/chatbot-flows", response_model=List[ChatbotFlowOut])
def re_list_chatbot_flows(
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    q = db.query(re_models.ChatbotFlow).filter(re_models.ChatbotFlow.tenant_id == int(tenant_id))
    if domain:
        q = q.filter(re_models.ChatbotFlow.domain == str(domain))
    rows = q.order_by(re_models.ChatbotFlow.updated_at.desc(), re_models.ChatbotFlow.id.desc()).all()
    return [_flow_to_out(r) for r in rows]

@router.post("/chatbot-flows", response_model=ChatbotFlowOut)
def re_upsert_chatbot_flow(
    payload: ChatbotFlowUpsertIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    svc = ChatbotFlowService(db)
    svc.validate_definition(payload.flow_definition)

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    domain = (payload.domain or "real_estate").strip() or "real_estate"

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

@router.post("/chatbot-flows/{flow_id}/publish", response_model=ChatbotFlowPublishOut)
def re_publish_chatbot_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = db.get(re_models.ChatbotFlow, int(flow_id))
    if not row or int(getattr(row, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="flow_not_found")

    svc = ChatbotFlowService(db)
    svc.validate_definition(row.flow_definition)

    current_max = (
        db.query(func.max(re_models.ChatbotFlow.published_version))
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == str(row.domain),
        )
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
def re_get_published_chatbot_flow(
    domain: str = "real_estate",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = (
        db.query(re_models.ChatbotFlow)
        .filter(
            re_models.ChatbotFlow.tenant_id == int(tenant_id),
            re_models.ChatbotFlow.domain == str(domain),
            re_models.ChatbotFlow.is_published == True,  # noqa: E712
        )
        .order_by(re_models.ChatbotFlow.published_version.desc(), re_models.ChatbotFlow.updated_at.desc())
        .first()
    )
    if not row:
        return ChatbotFlowPublishedCurrentOut(published=False, flow=None)
    return ChatbotFlowPublishedCurrentOut(published=True, flow=_flow_to_out(row))

@router.post("/chatbot-flows/publish-by-version", response_model=ChatbotFlowPublishOut)
def re_publish_chatbot_flow_by_version(
    payload: ChatbotFlowPublishByVersionIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    domain = (payload.domain or "real_estate").strip() or "real_estate"
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

@router.get("/chatbot-templates", response_model=List[ChatbotFlowTemplateOut])
def re_list_chatbot_flow_templates(
    tenant_id: int = Depends(require_admin_tenant_id),
):
    _ = tenant_id
    return list_chatbot_flow_templates()

@router.post("/chatbot-templates/apply", response_model=ChatbotFlowTemplateApplyOut)
def re_apply_chatbot_flow_template(
    payload: ChatbotFlowTemplateApplyIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    return apply_chatbot_flow_template(db=db, tenant_id=int(tenant_id), payload=payload)

@router.post("/chatbot-flows/{flow_id}/preview", response_model=ChatbotFlowPreviewOut)
def re_preview_chatbot_flow(
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
    state = normalize_state(
        state=loaded_state,
        sender_id=sender_id,
        tenant_id=int(tenant_id),
        default_stage=str(flow.start or "start"),
    )

    text_raw = payload.input or ""
    text_normalized = (payload.input or "").lower()

    engine = FlowEngine(db)
    out = engine.try_process_message_with_definition(
        flow_definition=row.flow_definition,
        sender_id=sender_id,
        text_raw=text_raw,
        text_normalized=text_normalized,
        state=state,
    )

    return ChatbotFlowPreviewOut(
        message=out.message,
        state=out.state or state,
        handled=bool(out.handled),
        continue_loop=bool(out.continue_loop),
    )

def _normalize_wa_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s
    # Aceitar entrada com @c.us
    if "@" in s:
        s = s.split("@", 1)[0]
    # Aceitar +55... removendo +
    if s.startswith("+"):
        s = s[1:]
    # manter somente dígitos
    s = "".join(ch for ch in s if ch.isdigit())
    return s

def _get_booking_recipients(tenant_settings: dict) -> list[str]:
    raw = tenant_settings.get("booking_notification_recipients")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    return []

def _get_booking_template_name(tenant_settings: dict) -> str | None:
    t = (tenant_settings.get("booking_notification_template") or "").strip()
    return t or None

class BookingRecipientsIn(BaseModel):
    recipients: list[str] = Field(default_factory=list)

class BookingRecipientsOut(BaseModel):
    recipients: list[str] = []

class BookingTemplateIn(BaseModel):
    template_name: str | None = None

class BookingTemplateOut(BaseModel):
    template_name: str | None = None

@router.get("/booking/recipients", response_model=BookingRecipientsOut)
def re_booking_get_recipients(db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    current = dict(getattr(tenant, "settings_json", {}) or {})
    return BookingRecipientsOut(recipients=_get_booking_recipients(current))

@router.put("/booking/recipients", response_model=BookingRecipientsOut)
def re_booking_set_recipients(payload: BookingRecipientsIn, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    current = dict(getattr(tenant, "settings_json", {}) or {})
    recipients = sorted({
        _normalize_wa_id(x) for x in (payload.recipients or []) if _normalize_wa_id(x)
    })
    current["booking_notification_recipients"] = recipients
    tenant.settings_json = current
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return BookingRecipientsOut(recipients=_get_booking_recipients(current))

@router.get("/booking/template", response_model=BookingTemplateOut)
def re_booking_get_template(db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    current = dict(getattr(tenant, "settings_json", {}) or {})
    return BookingTemplateOut(template_name=_get_booking_template_name(current))

@router.put("/booking/template", response_model=BookingTemplateOut)
def re_booking_set_template(payload: BookingTemplateIn, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    current = dict(getattr(tenant, "settings_json", {}) or {})
    name = (payload.template_name or "").strip() or None
    current["booking_notification_template"] = name
    tenant.settings_json = current
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return BookingTemplateOut(template_name=_get_booking_template_name(current))


def _format_booking_notification(visit: re_models.VisitSchedule, lead: re_models.Lead | None, prop: re_models.Property | None) -> str:
    lead_name = (getattr(lead, "name", None) or "-")
    lead_phone = (getattr(lead, "phone", None) or getattr(visit, "contact_phone", None) or "-")
    ref = ""
    if prop is not None:
        ref = getattr(prop, "ref_code", None) or getattr(prop, "external_id", None) or str(getattr(prop, "id", ""))
    dt = getattr(visit, "scheduled_datetime", None)
    dt_txt = dt.strftime("%d/%m/%Y %H:%M") if dt else "-"
    return (
        "📅 *Visita confirmada*\n"
        f"• Lead: {lead_name}\n"
        f"• Contato: {lead_phone}\n"
        f"• Imóvel: #{ref}\n"
        f"• Quando: {dt_txt}"
    )


class ConfirmVisitOut(BaseModel):
    visit_id: int
    visit_status: str
    lead_id: int | None = None
    lead_status: str | None = None
    notified: int = 0
    errors: list[dict] = []


class VisitListOut(BaseModel):
    id: int
    lead_id: int
    property_id: int
    status: str
    scheduled_datetime: str | None = None


@router.get("/visits", response_model=list[VisitListOut])
def re_list_visits(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(re_models.VisitSchedule).filter(re_models.VisitSchedule.tenant_id == int(tenant_id))
    if status:
        q = q.filter(re_models.VisitSchedule.status == status)
    rows = (
        q.order_by(re_models.VisitSchedule.id.desc())
        .limit(max(1, min(int(limit), 200)))
        .offset(max(0, int(offset)))
        .all()
    )
    out: list[VisitListOut] = []
    for v in rows:
        dt = getattr(v, "scheduled_datetime", None)
        out.append(
            VisitListOut(
                id=int(v.id),
                lead_id=int(v.lead_id),
                property_id=int(v.property_id),
                status=str(v.status),
                scheduled_datetime=(dt.isoformat() if dt else None),
            )
        )
    return out


@router.post("/visits/{visit_id}/confirm", response_model=ConfirmVisitOut)
def re_confirm_visit(visit_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    from app.services.visit_service import VisitService

    try:
        visit = VisitService.confirm_visit(db, int(visit_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})

    if int(getattr(visit, "tenant_id", 0) or 0) != int(tenant_id):
        raise HTTPException(status_code=404, detail="visit_not_found")

    lead = (
        db.query(re_models.Lead)
        .filter(re_models.Lead.tenant_id == int(tenant_id), re_models.Lead.id == int(visit.lead_id))
        .first()
        if getattr(visit, "lead_id", None)
        else None
    )
    prop = (
        db.query(re_models.Property)
        .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(visit.property_id))
        .first()
        if getattr(visit, "property_id", None)
        else None
    )

    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    settings_json = dict(getattr(tenant, "settings_json", {}) or {})
    recipients = _get_booking_recipients(settings_json)
    template_name = _get_booking_template_name(settings_json)

    provider = get_provider()
    notified = 0
    errors: list[dict] = []
    text = _format_booking_notification(visit, lead, prop)
    for raw in recipients:
        to = _normalize_wa_id(raw)
        if not to:
            continue
        try:
            # Preferir template para notificações internas (funciona fora da janela 24h)
            if template_name:
                provider.send_template(to, template_name, tenant_id=str(tenant.id))
            else:
                provider.send_text(to, text, tenant_id=str(tenant.id))
            notified += 1
        except Exception as e:
            # Não falhar a confirmação por erro de mensageria
            errors.append({"to": raw, "error": str(e)})

    return ConfirmVisitOut(
        visit_id=int(visit.id),
        visit_status=str(getattr(visit, "status", "")),
        lead_id=(int(getattr(lead, "id")) if lead is not None else None),
        lead_status=(str(getattr(lead, "status")) if lead is not None else None),
        notified=notified,
        errors=errors,
    )


# ===== Dependência DB (admin) =====
# Centralizado via app.api.deps.get_db


# ====== Gestão de imagens (admin) ======
class ReorderIn(BaseModel):
    items: list[dict]


@router.delete("/imoveis/{property_id}/imagens/{image_id}")
def admin_delete_image(
    property_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        res = delete_property_image(db, property_id, image_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})

@router.patch("/imoveis/{property_id}/imagens/{image_id}/capa")
def admin_set_cover(
    property_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        res = set_property_cover(db, property_id, image_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})

@router.post("/imoveis/{property_id}/imagens/reorder")
def admin_reorder_images(
    property_id: int,
    payload: ReorderIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        res = reorder_property_images(db, property_id, payload.items or [])
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": str(e)})

# ====== Gestão de imóvel (admin) ======
class SetActiveIn(BaseModel):
    ativo: bool = Field(...)


# ====== Backfill de ref_code (admin) ======
class BackfillRefCodeIn(BaseModel):
    provider: Literal["ndimoveis", "any"] = "ndimoveis"
    limit: int | None = Field(default=None, ge=1, le=5000)
    dry_run: bool = False


class BackfillRefCodeOut(BaseModel):
    targeted: int
    updated: int
    conflicts: list[dict] = []
    skipped_invalid: int = 0


@router.patch("/imoveis/{property_id}/ativo")
def admin_set_active(
    property_id: int,
    payload: SetActiveIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = set_active_property(db, property_id, payload.ativo, tenant_id=int(tenant_id))
        return {"ok": True, "id": prop.id, "ativo": bool(prop.is_active)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})

@router.post("/properties/backfill_ref_code", response_model=BackfillRefCodeOut)
def re_properties_backfill_ref_code(
    payload: BackfillRefCodeIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        stmt = (
            select(
                re_models.Property.id,
                re_models.Property.external_id,
                re_models.Property.ref_code,
            )
            .where(
                re_models.Property.tenant_id == tenant.id,
            )
        )
        if payload.provider != "any":
            stmt = stmt.where(re_models.Property.source == payload.provider)
        stmt = stmt.where(re_models.Property.ref_code.is_(None))
        stmt = stmt.where(re_models.Property.external_id.isnot(None))
        if payload.limit:
            stmt = stmt.limit(payload.limit)
        rows = db.execute(stmt).all()

        targeted = len(rows)
        updated = 0
        conflicts: list[dict] = []
        skipped_invalid = 0

        # Regex: letra + 2-6 dígitos (normalizado em ndimoveis.parse_detail)
        rx = re.compile(r"^[A-Za-z][0-9]{2,6}$")

        for pid, ext_id, _ in rows:
            eid = (ext_id or "").strip()
            if not eid or not rx.match(eid):
                skipped_invalid += 1
                continue

            exists_stmt = (
                select(re_models.Property.id)
                .where(
                    re_models.Property.tenant_id == tenant.id,
                    re_models.Property.ref_code == eid,
                )
                .limit(1)
            )
            existing = db.execute(exists_stmt).scalar_one_or_none()
            if existing and int(existing) != int(pid):
                conflicts.append({"property_id": pid, "conflict_with": int(existing), "ref_code": eid})
                continue

            if payload.dry_run:
                updated += 1
                continue

            prop = db.get(re_models.Property, int(pid))
            if prop and int(getattr(prop, "tenant_id", 0) or 0) == int(tenant.id):
                prop.ref_code = eid
                try:
                    db.add(prop)
                    db.commit()
                    updated += 1
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    conflicts.append({"property_id": pid, "error": str(e), "ref_code": eid})

        return BackfillRefCodeOut(
            targeted=targeted,
            updated=updated,
            conflicts=conflicts,
            skipped_invalid=skipped_invalid,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "backfill_ref_code_error", "message": str(e)})


@router.delete("/imoveis/{property_id}")
def admin_soft_delete_property(property_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    try:
        return soft_delete_property(db, property_id, tenant_id=int(tenant_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": str(e)})


@router.delete("/imoveis/{property_id}/hard")
def admin_hard_delete_property(property_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    try:
        return hard_delete_property(db, property_id, tenant_id=int(tenant_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"code": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": str(e)})


# ====== Exclusão em lote (admin) ======
class BulkDeleteIn(BaseModel):
    title_contains: str | None = None
    description_contains: str | None = None
    mode: str = "soft"


@router.post("/imoveis/bulk-delete")
def admin_bulk_delete_properties(payload: BulkDeleteIn, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        term_title = (payload.title_contains or "").strip()
        term_desc = (payload.description_contains or "").strip()
        if not term_title and not term_desc:
            raise HTTPException(status_code=400, detail="missing_filters")
        stmt = select(re_models.Property).where(re_models.Property.tenant_id == tenant.id)
        if term_title:
            stmt = stmt.where(re_models.Property.title.ilike(f"%{term_title}%"))
        if term_desc:
            stmt = stmt.where(re_models.Property.description.ilike(f"%{term_desc}%"))
        props = db.execute(stmt).scalars().all()
        deleted = 0
        for p in props:
            try:
                if (payload.mode or "soft").lower() == "hard":
                    hard_delete_property(db, int(p.id), tenant_id=int(tenant_id))
                else:
                    soft_delete_property(db, int(p.id), tenant_id=int(tenant_id))
                deleted += 1
            except Exception:
                continue
        return {"ok": True, "matched": len(props), "deleted": deleted, "mode": (payload.mode or "soft").lower()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "bulk_delete_error", "message": str(e)})


# ====== Enfileiramento assíncrono (MVP) ======
class NDRunIn(BaseModel):
    tenant_id: int
    urls: list[str]
    throttle_ms: int = 250


class EnqueueIn(NDRunIn):
    pass


class EnqueueOut(BaseModel):
    task_id: str
    status: Literal["queued", "running", "done", "error"]


class TaskStatusOut(BaseModel):
    task_id: str
    status: Literal["queued", "running", "done", "error"]
    result: dict | None = None
    error: str | None = None


def _background_run(task_id: str, payload: NDRunIn):
    TASKS[task_id] = {"status": "running", "result": None, "error": None}
    try:
        res = re_nd_run(payload)  # reutiliza a lógica síncrona
        TASKS[task_id] = {"status": "done", "result": res.model_dump(), "error": None}
    except HTTPException as he:
        TASKS[task_id] = {"status": "error", "result": None, "error": str(he.detail)}
    except Exception as e:
        TASKS[task_id] = {"status": "error", "result": None, "error": str(e)}


@router.post("/import/ndimoveis/enqueue", response_model=EnqueueOut)
def re_nd_enqueue(payload: EnqueueIn, bg: BackgroundTasks):
    import uuid
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "queued", "result": None, "error": None}
    bg.add_task(_background_run, task_id, payload)
    return EnqueueOut(task_id=task_id, status="queued")


@router.get("/import/status", response_model=TaskStatusOut)
def re_import_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="task_not_found")
    t = TASKS[task_id]
    return TaskStatusOut(task_id=task_id, status=t["status"], result=t.get("result"), error=t.get("error"))


# ====== Endpoints de auditoria ======
class RECountOut(BaseModel):
    total: int


@router.get("/properties/count", response_model=RECountOut)
def re_properties_count(
    source: str = "ndimoveis",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        stmt = select(re_models.Property).where(re_models.Property.tenant_id == tenant.id)
        if source:
            stmt = stmt.where(re_models.Property.source == source)
        # count(*) com SQLAlchemy 2.x
        from sqlalchemy import func
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        return RECountOut(total=int(total))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_count_error", "message": str(e)})


class RESampleItem(BaseModel):
    id: int
    external_id: str | None
    title: str = Field(serialization_alias="titulo")
    price: float = Field(serialization_alias="preco")


class RESampleOut(BaseModel):
    items: list[RESampleItem]


@router.get("/properties/sample", response_model=RESampleOut)
def re_properties_sample(
    source: str = "ndimoveis",
    limit: int = 10,
    order: Literal["created", "updated"] = "created",
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        stmt = (
            select(
                re_models.Property.id,
                re_models.Property.external_id,
                re_models.Property.title,
                re_models.Property.price,
            )
            .where(re_models.Property.tenant_id == tenant.id)
        )
        if source:
            stmt = stmt.where(re_models.Property.source == source)
        order_col = re_models.Property.created_at if order == "created" else re_models.Property.updated_at
        stmt = stmt.order_by(order_col.desc()).limit(max(1, min(limit, 50)))
        rows = db.execute(stmt).all()
        items = [
            RESampleItem(
                id=row[0],
                external_id=row[1],
                title=row[2],
                price=float(row[3] or 0.0),
            )
            for row in rows
        ]
        return RESampleOut(items=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_sample_error", "message": str(e)})


# ====== Meta por property_id (external_id/source) ======
class PropertyMetaOut(BaseModel):
    id: int
    external_id: str | None
    source: str | None = Field(serialization_alias="fonte")
    title: str | None = Field(serialization_alias="titulo")


@router.get("/properties/{property_id}/meta", response_model=PropertyMetaOut)
def re_property_meta(
    property_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        return PropertyMetaOut(id=prop.id, external_id=prop.external_id, source=prop.source, title=prop.title)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_property_meta_error", "message": str(e)})


# ====== Detalhes internos por property_id (admin) ======
class PropertyInternalOut(BaseModel):
    id: int
    external_id: str | None
    source: str | None = Field(serialization_alias="fonte")
    title: str | None = Field(serialization_alias="titulo")
    description: str | None = Field(serialization_alias="descricao")
    address_json: dict | None = Field(serialization_alias="endereco_json")


@router.get("/properties/{property_id}/internal", response_model=PropertyInternalOut)
def re_property_internal(
    property_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        return PropertyInternalOut(
            id=prop.id,
            external_id=prop.external_id,
            source=prop.source,
            title=prop.title,
            description=getattr(prop, "description", None),
            address_json=getattr(prop, "address_json", None),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_property_internal_error", "message": str(e)})


# ====== Verificação por external_id (admin) ======
class RECheckByExternalIn(BaseModel):
    external_ids: list[str]


class RECheckItem(BaseModel):
    external_id: str
    id: int | None = None
    has_description: bool = Field(default=False, serialization_alias="tem_descricao")
    description_len: int = Field(default=0, serialization_alias="tamanho_descricao")
    source_url: str | None = Field(default=None, serialization_alias="url_origem")


class RECheckByExternalOut(BaseModel):
    items: list[RECheckItem]


@router.post("/properties/check_by_external", response_model=RECheckByExternalOut)
def re_properties_check_by_external(
    payload: RECheckByExternalIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        out: list[RECheckItem] = []
        ext_ids = [str(e).strip() for e in (payload.external_ids or []) if str(e).strip()]
        if not ext_ids:
            return RECheckByExternalOut(items=[])
        for eid in ext_ids:
            stmt = (
                select(re_models.Property)
                .where(
                    re_models.Property.tenant_id == int(tenant_id),
                    re_models.Property.source == "ndimoveis",
                    re_models.Property.external_id == eid,
                )
                .limit(1)
            )
            prop = db.execute(stmt).scalar_one_or_none()
            if not prop:
                out.append(RECheckItem(external_id=eid))
                continue
            desc = getattr(prop, "description", None) or ""
            data = getattr(prop, "address_json", None) or {}
            out.append(
                RECheckItem(
                    external_id=eid,
                    id=prop.id,
                    has_description=bool(desc.strip()),
                    description_len=len(desc or ""),
                    source_url=str(data.get("source_url") or None),
                )
            )
        return RECheckByExternalOut(items=out)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_check_by_external_error", "message": str(e)})


# ====== Repair por property_id (ND Imóveis) ======
class RepairByIdIn(BaseModel):
    property_id: int
    max_pages_per_finalidade: int = Field(default=6, ge=1, le=20)
    throttle_ms: int = Field(default=300, ge=0)


class RepairByIdOut(BaseModel):
    repaired: bool
    images_created: int
    external_id: str | None = None
    url: str | None = None


@router.post("/import/ndimoveis/repair_by_id", response_model=RepairByIdOut)
def re_nd_repair_by_id(payload: RepairByIdIn, db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    try:
        prop = (
            db.query(re_models.Property)
            .filter(re_models.Property.tenant_id == int(tenant_id), re_models.Property.id == int(payload.property_id))
            .first()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="property_not_found")
        if (prop.source or "").lower() != "ndimoveis":
            raise HTTPException(status_code=400, detail="unsupported_source")
        if not prop.external_id:
            raise HTTPException(status_code=400, detail="external_id_missing")

        target_eid = str(prop.external_id)
        fins = ["venda", "locacao"]
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            for fin in fins:
                for page in range(1, payload.max_pages_per_finalidade + 1):
                    for list_url in _nd_list_url_candidates(fin, page):
                        try:
                            lr = client.get(list_url)
                            if lr.status_code != 200:
                                continue
                            links = _extract_detail_links(lr.text)
                        except Exception:
                            links = []
                        finally:
                            time.sleep(payload.throttle_ms / 1000.0)
                        for durl in links:
                            try:
                                dr = client.get(durl)
                                if dr.status_code != 200:
                                    continue
                                dto = nd.parse_detail(dr.text, durl)
                                if dto.external_id and str(dto.external_id) == target_eid:
                                    st, imgs = upsert_property(db, int(tenant_id), dto)
                                    db.commit()
                                    return RepairByIdOut(repaired=True, images_created=imgs, external_id=target_eid, url=durl)
                            except Exception:
                                continue
                            finally:
                                time.sleep(payload.throttle_ms / 1000.0)
        # não achou nas páginas escaneadas
        return RepairByIdOut(repaired=False, images_created=0, external_id=target_eid, url=None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_by_id_error", "message": str(e)})


# ====== Repair de preços (corrige apenas o campo price) ======
class RepairPricesIn(BaseModel):
    source: str = Field(default="ndimoveis")
    limit: int = Field(default=50, ge=1, le=200)
    max_pages_per_finalidade: int = Field(default=5, ge=1, le=20)
    throttle_ms: int = Field(default=300, ge=0)


class RepairPricesOut(BaseModel):
    targeted: int
    updated_prices: int
    not_found: list[str]


@router.post("/repair/prices", response_model=RepairPricesOut)
def re_repair_prices(
    payload: RepairPricesIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        # Seleciona últimos N imóveis pela data de atualização (prioridade) do source
        stmt = (
            select(
                re_models.Property.id,
                re_models.Property.external_id,
            )
            .where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == payload.source,
            )
            .order_by(re_models.Property.updated_at.desc())
            .limit(payload.limit)
        )
        rows = db.execute(stmt).all()
        target_ext_ids = [r[1] for r in rows if r[1]]

        # Descobrir URLs nas primeiras páginas e montar mapa ext_id -> dto
        fins = ["venda", "locacao"]
        found_map: dict[str, dict] = {}
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            for fin in fins:
                for page in range(1, payload.max_pages_per_finalidade + 1):
                    for url in _nd_list_url_candidates(fin, page):
                        try:
                            r = client.get(url)
                            if r.status_code != 200:
                                continue
                            links = _extract_detail_links(r.text)
                        except Exception:
                            links = []
                        finally:
                            time.sleep(payload.throttle_ms / 1000.0)
                        for durl in links:
                            try:
                                dr = client.get(durl)
                                if dr.status_code != 200:
                                    continue
                                dto = nd.parse_detail(dr.text, durl)
                                if dto.external_id:
                                    if dto.external_id in target_ext_ids:
                                        found_map[dto.external_id] = {
                                            "price": dto.price,
                                            "purpose": dto.purpose,
                                        }
                            except Exception:
                                continue
                            finally:
                                time.sleep(payload.throttle_ms / 1000.0)

        # Atualizar apenas o campo price
        updated = 0
        not_found: list[str] = []
        for eid in target_ext_ids:
            info = found_map.get(eid)
            if not info:
                not_found.append(eid)
                continue
            new_price = float(info.get("price") or 0.0)
            new_purpose = info.get("purpose")
            if new_price <= 0:
                # Mesmo sem preço válido, ainda podemos corrigir finalidade
                pass
            stmt = select(re_models.Property).where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == payload.source,
                re_models.Property.external_id == eid,
            )
            prop = db.execute(stmt).scalar_one_or_none()
            if not prop:
                continue
            changed = False
            if new_price > 0 and prop.price != new_price:
                prop.price = new_price
                changed = True
            if isinstance(new_purpose, str) and new_purpose in ("sale", "rent"):
                # Atualiza finalidade se divergente
                try:
                    from app.domain.realestate.models import PropertyPurpose as _PP

                    new_pp = _PP(new_purpose)
                    if getattr(prop, "purpose", None) != new_pp:
                        prop.purpose = new_pp
                        changed = True
                except Exception:
                    pass
            if changed:
                db.add(prop)
                updated += 1
        if updated:
            db.commit()

        return RepairPricesOut(targeted=len(target_ext_ids), updated_prices=updated, not_found=not_found[:50])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_prices_error", "message": str(e)})


# ====== Repair de finalidade (purpose) a partir do título ======
class RepairPurposeIn(BaseModel):
    source: str = Field(default="ndimoveis")
    cidade: str | None = None
    estado: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    dry_run: bool = Field(default=False)


class RepairPurposeOut(BaseModel):
    targeted: int
    updated: int
    unchanged: int
    examples: list[dict] = []


@router.post("/repair/purpose_from_title", response_model=RepairPurposeOut)
def re_repair_purpose_from_title(
    payload: RepairPurposeIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        stmt = (
            select(
                re_models.Property.id,
                re_models.Property.title,
                re_models.Property.purpose,
                re_models.Property.address_city,
                re_models.Property.address_state,
            )
            .where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == payload.source,
            )
            .order_by(re_models.Property.updated_at.desc())
            .limit(payload.limit)
        )
        if payload.cidade:
            stmt = stmt.where(re_models.Property.address_city.ilike(f"%{payload.cidade.strip()}%"))
        if payload.estado:
            stmt = stmt.where(re_models.Property.address_state == payload.estado.strip().upper())

        rows = db.execute(stmt).all()
        targeted = len(rows)
        updated = 0
        unchanged = 0
        examples: list[dict] = []

        # Função simples para inferir finalidade com base no título
        import re as _re

        def infer_purpose(title: str | None) -> str | None:
            if not title:
                return None
            t = title.lower()
            if _re.search(r"loca[cç][aã]o|alug", t):
                return "rent"
            if _re.search(r"venda", t):
                return "sale"
            return None

        if not payload.dry_run:
            for rid, title, purpose, city, state in rows:
                new_p = infer_purpose(title)
                if new_p is None:
                    unchanged += 1
                    continue
                try:
                    from app.domain.realestate.models import PropertyPurpose as _PP

                    new_pp = _PP(new_p)
                except Exception:
                    unchanged += 1
                    continue
                prop = (
                    db.query(re_models.Property)
                    .filter(re_models.Property.tenant_id == tenant.id, re_models.Property.id == int(rid))
                    .first()
                )
                if not prop:
                    unchanged += 1
                    continue
                if getattr(prop, "purpose", None) != new_pp:
                    prop.purpose = new_pp
                    db.add(prop)
                    updated += 1
                    if len(examples) < 10:
                        examples.append(
                            {
                                "id": rid,
                                "titulo": title,
                                "from": str(purpose),
                                "to": new_p,
                                "cidade": city,
                                "estado": state,
                            }
                        )
                else:
                    unchanged += 1
            if updated:
                db.commit()
        else:
            # Apenas simula (dry run)
            for rid, title, purpose, city, state in rows:
                new_p = infer_purpose(title)
                if new_p and len(examples) < 10:
                    examples.append(
                        {
                            "id": rid,
                            "titulo": title,
                            "from": str(purpose),
                            "to": new_p,
                            "cidade": city,
                            "estado": state,
                        }
                    )

        return RepairPurposeOut(targeted=targeted, updated=updated, unchanged=unchanged, examples=examples)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_purpose_error", "message": str(e)})


# ====== Repair de imagens inválidas ======
class RepairImagesIn(BaseModel):
    source: str = Field(default="ndimoveis")
    cidade: str | None = None
    estado: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    dry_run: bool = Field(default=False)


class RepairImagesOut(BaseModel):
    properties_checked: int
    images_removed: int
    properties_updated: int
    examples: list[dict] = []


def _is_valid_image_url(url: str | None) -> bool:
    """Valida se a URL da imagem tem domínio válido."""
    if not url:
        return False
    try:
        u = str(url).strip()
        if not (u.startswith('http://') or u.startswith('https://')):
            return False
        from urllib.parse import urlparse
        parsed = urlparse(u)
        # Verifica se tem hostname e se contém pelo menos um ponto (domínio válido)
        return bool(parsed.hostname and '.' in parsed.hostname)
    except Exception:
        return False


@router.post("/images/repair_invalid", response_model=RepairImagesOut)
def re_repair_invalid_images(
    payload: RepairImagesIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    """
    Remove imagens com URLs inválidas (sem domínio válido) e promove 
    uma imagem válida como capa quando necessário.
    """
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")

        # Buscar imóveis
        stmt = (
            select(re_models.Property.id)
            .where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == payload.source,
            )
            .order_by(re_models.Property.updated_at.desc())
            .limit(payload.limit)
        )
        if payload.cidade:
            stmt = stmt.where(re_models.Property.address_city.ilike(f"%{payload.cidade.strip()}%"))
        if payload.estado:
            stmt = stmt.where(re_models.Property.address_state == payload.estado.strip().upper())

        property_ids = [row[0] for row in db.execute(stmt).all()]

        properties_checked = len(property_ids)
        images_removed = 0
        properties_updated = 0
        examples: list[dict] = []

        for prop_id in property_ids:
            # Buscar imagens do imóvel
            img_stmt = (
                select(re_models.PropertyImage)
                .where(re_models.PropertyImage.property_id == prop_id)
                .order_by(re_models.PropertyImage.sort_order)
            )
            images = db.execute(img_stmt).scalars().all()

            if not images:
                continue

            # Separar válidas e inválidas
            invalid_images = [img for img in images if not _is_valid_image_url(img.url)]
            valid_images = [img for img in images if _is_valid_image_url(img.url)]

            if not invalid_images:
                continue

            property_changed = False

            if not payload.dry_run:
                # Remover imagens inválidas
                for img in invalid_images:
                    db.delete(img)
                    images_removed += 1
                    property_changed = True

                # Se havia capa inválida e existem imagens válidas, promover a primeira válida
                had_invalid_cover = any(img.is_cover for img in invalid_images)
                if had_invalid_cover and valid_images:
                    # Remover flag de capa de todas
                    for img in valid_images:
                        img.is_cover = False
                    # Promover primeira válida
                    valid_images[0].is_cover = True
                    db.add(valid_images[0])
                    property_changed = True

            if property_changed or payload.dry_run:
                properties_updated += 1
                if len(examples) < 10:
                    prop = (
                        db.query(re_models.Property)
                        .filter(re_models.Property.tenant_id == tenant.id, re_models.Property.id == int(prop_id))
                        .first()
                    )
                    examples.append(
                        {
                            "property_id": prop_id,
                            "titulo": prop.title if prop else None,
                            "invalid_urls": [img.url for img in invalid_images[:3]],
                            "invalid_count": len(invalid_images),
                            "valid_count": len(valid_images),
                        }
                    )

        if not payload.dry_run and images_removed > 0:
            db.commit()

        return RepairImagesOut(
            properties_checked=properties_checked,
            images_removed=images_removed if not payload.dry_run else 0,
            properties_updated=properties_updated,
            examples=examples,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_images_error", "message": str(e)})


# ====== Reset (limpeza) de imóveis e imagens por fonte ======
class REResetIn(BaseModel):
    source: str = Field(default="ndimoveis")
    dry_run: bool = Field(default=True)
    confirm: str | None = Field(default=None, description="Use 'CONFIRM' para executar sem dry_run")


class REResetOut(BaseModel):
    source: str
    dry_run: bool
    properties_total: int
    images_total: int
    deleted_properties: int
    deleted_images: int


@router.post("/properties/reset", response_model=REResetOut)
def re_properties_reset(
    payload: REResetIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    """
    Remove TODOS os imóveis e imagens da fonte informada apenas para o tenant padrão.
    - dry_run=True: apenas retorna as contagens (não deleta nada)
    - Para executar a exclusão, envie confirm="CONFIRM" e dry_run=False
    """
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")

        # Coletar IDs de imóveis por tenant+source
        p_stmt = select(re_models.Property.id).where(re_models.Property.tenant_id == tenant.id)
        if payload.source:
            p_stmt = p_stmt.where(re_models.Property.source == payload.source)
        prop_ids = [row[0] for row in db.execute(p_stmt).all()]

        if not prop_ids:
            return REResetOut(
                source=payload.source,
                dry_run=bool(payload.dry_run),
                properties_total=0,
                images_total=0,
                deleted_properties=0,
                deleted_images=0,
            )

        # Contar imagens relacionadas
        img_total = db.execute(select(func.count()).where(re_models.PropertyImage.property_id.in_(prop_ids))).scalar_one()

        if payload.dry_run:
            return REResetOut(
                source=payload.source,
                dry_run=True,
                properties_total=len(prop_ids),
                images_total=int(img_total),
                deleted_properties=0,
                deleted_images=0,
            )

        if payload.confirm != "CONFIRM":
            raise HTTPException(
                status_code=400,
                detail={"code": "confirm_required", "message": "Envie confirm='CONFIRM' para executar sem dry_run"},
            )

        # Executar deleção em transação
        del_imgs_stmt = delete(re_models.PropertyImage).where(re_models.PropertyImage.property_id.in_(prop_ids))
        del_props_stmt = delete(re_models.Property).where(re_models.Property.id.in_(prop_ids))

        deleted_images_count = db.execute(del_imgs_stmt).rowcount
        deleted_properties_count = db.execute(del_props_stmt).rowcount

        db.commit()

        return REResetOut(
            source=payload.source,
            dry_run=False,
            properties_total=len(prop_ids),
            images_total=int(img_total),
            deleted_properties=deleted_properties_count,
            deleted_images=deleted_images_count,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_reset_error", "message": str(e)})


# ====== Importar por URLs explícitas (ND Imóveis) ======

class NDFromUrlsIn(BaseModel):
    urls: list[str]
    throttle_ms: int = 250


class NDFromUrlsOut(BaseModel):
    created: int
    updated: int
    images_created: int
    processed: int
    sampled_external_ids: list[str]
    errors: list[dict] = []


@router.post("/import/ndimoveis/from_urls", response_model=NDFromUrlsOut)
def re_nd_import_from_urls(
    payload: NDFromUrlsIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        if not payload.urls:
            return NDFromUrlsOut(created=0, updated=0, images_created=0, processed=0, sampled_external_ids=[], errors=[])
        created = updated = images_created = processed = 0
        sample_ids: list[str] = []
        errs: list[dict] = []
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            tenant = db.get(Tenant, int(tenant_id))
            if not tenant:
                raise HTTPException(status_code=404, detail="tenant_not_found")
            for url in payload.urls:
                try:
                    r = client.get(url)
                    if r.status_code != 200:
                        errs.append({"url": url, "status": r.status_code})
                        continue
                    dto = nd.parse_detail(r.text, url)
                    if dto.external_id:
                        sample_ids.append(dto.external_id)
                    st, imgs = upsert_property(db, int(tenant.id), dto)
                    if st == "created":
                        created += 1
                    else:
                        updated += 1
                    images_created += imgs
                    processed += 1
                except Exception as e:  # noqa: BLE001
                    errs.append({"url": url, "error": str(e)})
                finally:
                    time.sleep(max(0, payload.throttle_ms) / 1000.0)
            db.commit()
        return NDFromUrlsOut(
            created=created,
            updated=updated,
            images_created=images_created,
            processed=processed,
            sampled_external_ids=sample_ids[:20],
            errors=errs[:20],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "nd_from_urls_error", "message": str(e)})


# ====== Backfill em massa (SEGURO) - processa todos os imóveis da base ======
class NDBackfillAllIn(BaseModel):
    max_pages_per_finalidade: int = Field(default=50, ge=1, le=100)
    throttle_ms: int = Field(default=300, ge=100)
    limit_properties: int | None = Field(default=None, ge=1, le=1000)


class NDBackfillAllOut(BaseModel):
    task_id: str
    status: str
    total_properties: int


@router.post("/import/ndimoveis/backfill_all", response_model=NDBackfillAllOut)
def re_nd_backfill_all(
    payload: NDBackfillAllIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    """
    Processa TODOS os imóveis da base (source=ndimoveis) em background:
    - Para cada imóvel, busca external_id
    - Varre páginas da ND procurando o detalhe
    - Atualiza SOMENTE description (se vazia) e address_json.source_url
    - Não altera: preço, tipo, finalidade, imagens
    """
    import uuid
    task_id = str(uuid.uuid4())

    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    stmt = select(re_models.Property.id, re_models.Property.external_id).where(
        re_models.Property.tenant_id == tenant.id,
        re_models.Property.source == "ndimoveis",
    )
    if payload.limit_properties:
        stmt = stmt.limit(payload.limit_properties)
    rows = db.execute(stmt).all()
    total = len(rows)

    TASKS[task_id] = {"status": "queued", "result": None, "error": None, "total": total}

    def _run_backfill():
        TASKS[task_id]["status"] = "running"
        try:
            processed = matched = upd_desc = upd_link = 0
            not_found: list[str] = []
            
            with httpx.Client(timeout=30.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
                for prop_id, ext_id in rows:
                    if not ext_id:
                        continue
                    
                    # Varre páginas procurando este external_id
                    found_url: str | None = None
                    for fin in ["venda", "locacao"]:
                        if found_url:
                            break
                        for page in range(1, payload.max_pages_per_finalidade + 1):
                            for list_url in _nd_list_url_candidates(fin, page):
                                try:
                                    lr = client.get(list_url)
                                    if lr.status_code != 200:
                                        continue
                                    links = _extract_detail_links(lr.text)
                                except Exception:
                                    links = []
                                finally:
                                    time.sleep(payload.throttle_ms / 1000.0)
                                
                                for durl in links:
                                    try:
                                        dr = client.get(durl)
                                        if dr.status_code != 200:
                                            continue
                                        dto = nd.parse_detail(dr.text, durl)
                                        if dto.external_id and str(dto.external_id) == str(ext_id):
                                            found_url = durl
                                            break
                                    except Exception:
                                        continue
                                    finally:
                                        time.sleep(payload.throttle_ms / 1000.0)
                                
                                if found_url:
                                    break
                            if found_url:
                                break
                    
                    if not found_url:
                        not_found.append(str(ext_id))
                        continue
                    
                    # Atualiza via from_urls_safe logic
                    with db_session() as db2:
                        try:
                            r = client.get(found_url)
                            if r.status_code != 200:
                                continue
                            dto = nd.parse_detail(r.text, found_url)
                            
                            stmt = (
                                select(re_models.Property)
                                .where(
                                    re_models.Property.tenant_id == tenant.id,
                                    re_models.Property.source == "ndimoveis",
                                    re_models.Property.external_id == ext_id,
                                )
                                .limit(1)
                            )
                            prop = db2.execute(stmt).scalar_one_or_none()
                            if not prop:
                                continue
                            
                            matched += 1
                            changed = False
                            incoming_desc = getattr(dto, "description", None)
                            if incoming_desc and incoming_desc.strip():
                                if not (getattr(prop, "description", None) or "").strip():
                                    prop.description = incoming_desc.strip()
                                    upd_desc += 1
                                    changed = True
                            
                            data = dict(getattr(prop, "address_json", None) or {})
                            if not data.get("source_url"):
                                data["source_url"] = found_url
                                prop.address_json = data
                                upd_link += 1
                                changed = True
                            
                            if changed:
                                db2.add(prop)
                                db2.commit()
                            processed += 1
                        except Exception:
                            continue
            
            TASKS[task_id] = {
                "status": "done",
                "result": {
                    "processed": processed,
                    "matched": matched,
                    "updated_descriptions": upd_desc,
                    "updated_links": upd_link,
                    "not_found": not_found[:100],
                },
                "error": None,
            }
        except Exception as e:
            TASKS[task_id] = {"status": "error", "result": None, "error": str(e)}
    
    bg.add_task(_run_backfill)
    return NDBackfillAllOut(task_id=task_id, status="queued", total_properties=total)


# ====== Verificar progresso do backfill (query direta no banco) ======
class BackfillProgressOut(BaseModel):
    total_properties: int
    with_description: int
    without_description: int
    with_source_url: int
    without_source_url: int
    sample_with_desc: list[dict] = []
    sample_without_desc: list[dict] = []


@router.get("/import/ndimoveis/backfill_progress", response_model=BackfillProgressOut)
def re_nd_backfill_progress(db: Session = Depends(get_db), tenant_id: int = Depends(require_admin_tenant_id)):
    """Consulta direta no banco para ver quantos imóveis já têm descrição e source_url preenchidos."""
    with contextlib.nullcontext(db) as db:
        tenant = db.get(Tenant, int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="tenant_not_found")
        
        # Total
        total = db.execute(
            select(func.count(re_models.Property.id)).where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == "ndimoveis",
            )
        ).scalar_one()
        
        # Com descrição (não nula e não vazia)
        with_desc = db.execute(
            select(func.count(re_models.Property.id)).where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == "ndimoveis",
                re_models.Property.description.isnot(None),
                re_models.Property.description != "",
            )
        ).scalar_one()
        
        # Com source_url
        with_url = db.execute(
            select(func.count(re_models.Property.id)).where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == "ndimoveis",
                re_models.Property.address_json.isnot(None),
            )
        ).scalar_one()
        
        # Amostra COM descrição (últimos 5)
        sample_with = db.execute(
            select(re_models.Property.id, re_models.Property.external_id, re_models.Property.description)
            .where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == "ndimoveis",
                re_models.Property.description.isnot(None),
                re_models.Property.description != "",
            )
            .order_by(re_models.Property.updated_at.desc())
            .limit(5)
        ).all()
        
        # Amostra SEM descrição (primeiros 5)
        sample_without = db.execute(
            select(re_models.Property.id, re_models.Property.external_id)
            .where(
                re_models.Property.tenant_id == tenant.id,
                re_models.Property.source == "ndimoveis",
                (re_models.Property.description.is_(None)) | (re_models.Property.description == ""),
            )
            .limit(5)
        ).all()
        
        return BackfillProgressOut(
            total_properties=total,
            with_description=with_desc,
            without_description=total - with_desc,
            with_source_url=with_url,
            without_source_url=total - with_url,
            sample_with_desc=[{"id": r[0], "external_id": r[1], "desc_length": len(r[2] or "")} for r in sample_with],
            sample_without_desc=[{"id": r[0], "external_id": r[1]} for r in sample_without],
        )
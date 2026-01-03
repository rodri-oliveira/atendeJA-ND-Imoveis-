from __future__ import annotations
import random
import time
import structlog
from celery import Task
from app.core.config import settings
from app.domain.policies import within_business_hours
from app.repositories.db import SessionLocal
from app.repositories import models
from app.messaging.provider import get_provider
from .celery_app import celery

log = structlog.get_logger()


class TransientSendError(Exception):
    pass


def _should_retry(status_code: int) -> bool:
    return status_code >= 500


def _backoff(retry_count: int) -> float:
    base = 2 ** max(0, retry_count)
    jitter = random.uniform(0, 0.2 * base)
    return min(30.0, base + jitter)


def _resolve_tenant(db, raw_tenant_id) -> models.Tenant | None:
    tid = str(raw_tenant_id or "").strip()
    if not tid:
        return None
    try:
        t_int = int(tid)
        return db.get(models.Tenant, t_int)
    except Exception:
        pass
    if (settings.APP_ENV or "").lower() == "prod":
        return None
    return db.query(models.Tenant).filter(models.Tenant.name == tid).first()


@celery.task(name="outbound.send_text", bind=True, max_retries=5)
def send_text(self: Task, tenant_id: str, to_wa_id: str, text: str, idempotency_key: str | None = None) -> dict:
    # Respect business hours (simple policy for now)
    if not within_business_hours():
        log.info("outbound_skipped_off_hours", tenant_id=tenant_id, to=to_wa_id)
        return {"status": "scheduled"}

    with SessionLocal() as db:
        tenant = _resolve_tenant(db, tenant_id)
        if tenant is None:
            return {"status": "error", "error": "tenant_not_found"}

        # Idempotency guard
        if idempotency_key:
            existing = (
                db.query(models.Message)
                .filter(
                    models.Message.tenant_id == tenant.id,
                    models.Message.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                log.info("outbound_idempotent_skip", tenant_id=tenant_id, key=idempotency_key)
                return {"status": "duplicate"}

        # Create conversation on demand (outbound-only)
        contact = (
            db.query(models.Contact)
            .filter(models.Contact.tenant_id == tenant.id, models.Contact.wa_id == to_wa_id)
            .first()
        )
        if contact is None:
            contact = models.Contact(tenant_id=tenant.id, wa_id=to_wa_id)
            db.add(contact)
            db.flush()

        convo = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.tenant_id == tenant.id,
                models.Conversation.contact_id == contact.id,
                models.Conversation.status != models.ConversationStatus.closed,
            )
            .order_by(models.Conversation.id.desc())
            .first()
        )
        if convo is None:
            convo = models.Conversation(tenant_id=tenant.id, contact_id=contact.id)
            db.add(convo)
            db.flush()

        # Record message as queued
        msg = models.Message(
            tenant_id=tenant.id,
            conversation_id=convo.id,
            direction=models.MessageDirection.outbound,
            type="text",
            payload={"text": text},
            status="queued",
            idempotency_key=idempotency_key,
        )
        db.add(msg)
        db.commit()

    try:
        provider = get_provider()
        resp = provider.send_text(to=to_wa_id, text=text, tenant_id=str(int(tenant.id)))
    except Exception as e:
        retry_no = self.request.retries
        delay = _backoff(retry_no)
        log.warning("outbound_retry", retries=retry_no + 1, delay=delay)
        raise self.retry(exc=TransientSendError(str(e)), countdown=delay)

    # Mark as sent
    with SessionLocal() as db:
        last = (
            db.query(models.Message)
            .filter(models.Message.tenant_id == tenant.id)
            .order_by(models.Message.id.desc())
            .first()
        )
        if last is not None and last.status == "queued":
            last.status = "sent"
            last.payload = {**(last.payload or {}), "wa_response": resp}
            db.add(last)
            db.commit()

    return {"status": "sent", "response": resp}


@celery.task(name="outbound.send_template", bind=True, max_retries=5)
def send_template(
    self: Task,
    tenant_id: str,
    to_wa_id: str,
    template_name: str,
    language_code: str = "pt_BR",
    components: list[dict] | None = None,
    idempotency_key: str | None = None,
) -> dict:
    # Template messages podem ser enviadas fora do horário, mas mantemos a mesma política por simplicidade
    if not within_business_hours():
        log.info("outbound_template_skipped_off_hours", tenant_id=tenant_id, to=to_wa_id)
        return {"status": "scheduled"}

    with SessionLocal() as db:
        tenant = _resolve_tenant(db, tenant_id)
        if tenant is None:
            return {"status": "error", "error": "tenant_not_found"}

        if idempotency_key:
            existing = (
                db.query(models.Message)
                .filter(
                    models.Message.tenant_id == tenant.id,
                    models.Message.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                log.info("outbound_template_idempotent_skip", tenant_id=tenant_id, key=idempotency_key)
                return {"status": "duplicate"}

        contact = (
            db.query(models.Contact)
            .filter(models.Contact.tenant_id == tenant.id, models.Contact.wa_id == to_wa_id)
            .first()
        )
        if contact is None:
            contact = models.Contact(tenant_id=tenant.id, wa_id=to_wa_id)
            db.add(contact)
            db.flush()

        convo = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.tenant_id == tenant.id,
                models.Conversation.contact_id == contact.id,
                models.Conversation.status != models.ConversationStatus.closed,
            )
            .order_by(models.Conversation.id.desc())
            .first()
        )
        if convo is None:
            convo = models.Conversation(tenant_id=tenant.id, contact_id=contact.id)
            db.add(convo)
            db.flush()

        msg = models.Message(
            tenant_id=tenant.id,
            conversation_id=convo.id,
            direction=models.MessageDirection.outbound,
            type="template",
            payload={
                "template": template_name,
                "language_code": language_code,
                "components": components or [],
            },
            status="queued",
            idempotency_key=idempotency_key,
        )
        db.add(msg)
        db.commit()

    try:
        provider = get_provider()
        resp = provider.send_template(
            to=to_wa_id,
            template_name=template_name,
            language=language_code,
            components=components,
            tenant_id=str(int(tenant.id)),
        )
    except Exception as e:
        retry_no = self.request.retries
        delay = _backoff(retry_no)
        log.warning("outbound_template_retry", retries=retry_no + 1, delay=delay)
        raise self.retry(exc=TransientSendError(str(e)), countdown=delay)

    with SessionLocal() as db:
        last = (
            db.query(models.Message)
            .filter(models.Message.tenant_id == tenant.id)
            .order_by(models.Message.id.desc())
            .first()
        )
        if last is not None and last.status == "queued":
            last.status = "sent"
            last.payload = {**(last.payload or {}), "wa_response": resp}
            db.add(last)
            db.commit()

    return {"status": "sent", "response": resp}

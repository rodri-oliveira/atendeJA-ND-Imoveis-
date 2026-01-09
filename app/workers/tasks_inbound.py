from __future__ import annotations
from datetime import timedelta
import json
import structlog
import redis
from app.core.config import settings
from .celery_app import celery
from app.repositories.db import db_session
from app.repositories import models

log = structlog.get_logger()

# Aggregation settings (can be made per-tenant later)
AGG_WINDOW_SECONDS = 2
MAX_COMPOSE_LEN = 1200


def _redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _agg_key(tenant_id: str, wa_id: str) -> str:
    return f"agg:{tenant_id}:{wa_id}"


def _compose(prev: str, new: str) -> str:
    if not prev:
        return new
    # Add space if needed
    sep = "" if prev.endswith((" ", "\n")) else " "
    out = (prev + sep + new).strip()
    if len(out) > MAX_COMPOSE_LEN:
        return out[:MAX_COMPOSE_LEN]
    return out


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


@celery.task(name="inbound.buffer")
def buffer_incoming_message(tenant_id: str, wa_id: str, text: str, raw_event: dict) -> None:
    r = _redis()
    key = _agg_key(tenant_id, wa_id)
    pipe = r.pipeline()
    # Compose buffered text
    existing = r.hget(key, "text") or ""
    composed = _compose(existing, text)
    pipe.hset(key, mapping={"text": composed, "raw": json.dumps(raw_event)})
    # Set/refresh TTL as aggregation window
    pipe.expire(key, AGG_WINDOW_SECONDS)
    pipe.execute()
    log.info("inbound_buffered", key=key, len=len(composed))
    # Schedule flush after window using countdown; idempotent by key
    flush_incoming_message.apply_async((tenant_id, wa_id), countdown=AGG_WINDOW_SECONDS)


@celery.task(name="inbound.flush")
def flush_incoming_message(tenant_id: str, wa_id: str) -> None:
    r = _redis()
    key = _agg_key(tenant_id, wa_id)
    # If key still exists, window expired and we can flush
    if not r.exists(key):
        return
    data = r.hgetall(key)
    text = data.get("text") or ""
    raw = data.get("raw")
    # Delete first to avoid duplicate flushes
    r.delete(key)
    log.info("inbound_flushed", key=key, text_len=len(text))
    # Normalize: resolve/create Contact & Conversation and register Message
    with db_session() as db:
        tenant = _resolve_tenant(db, tenant_id)
        if tenant is None:
            log.error("tenant_not_found", tenant_id=tenant_id)
            return

        contact = (
            db.query(models.Contact)
            .filter(models.Contact.tenant_id == tenant.id, models.Contact.wa_id == wa_id)
            .first()
        )
        if contact is None:
            contact = models.Contact(tenant_id=tenant.id, wa_id=wa_id)
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
            convo = models.Conversation(
                tenant_id=tenant.id,
                contact_id=contact.id,
            )
            db.add(convo)
            db.flush()

        msg = models.Message(
            tenant_id=tenant.id,
            conversation_id=convo.id,
            direction=models.MessageDirection.inbound,
            type="text",
            payload={"text": text, "raw": json.loads(raw) if raw else {}},
            status="received",
        )
        db.add(msg)
        db.commit()
    # If conversation is human_handoff, we stop here; otherwise, state machine would be called next.
    return

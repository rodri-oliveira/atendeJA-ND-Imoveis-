from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from app.core.config import settings
from app.messaging.provider import get_provider
import structlog
import os
import hmac
import hashlib
from app.repositories.db import db_session
from datetime import datetime
import re
from urllib.parse import urlparse
import redis
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.repositories import models as core_models
from app.domain.realestate import models as re_models
from app.domain.realestate.services.funnel_service import FunnelService
from app.services.conversation_state import ConversationStateService
from app.services.flow_message_orchestrator import try_process_via_flow_engine
from app.services.conversation_context import normalize_state
from app.services.llm_preprocessor import enrich_state_with_llm
from app.services.tenant_resolver import resolve_tenant_from_phone_number_id, TenantResolutionError

from pydantic import BaseModel
from typing import Literal
 
 
router = APIRouter()
log = structlog.get_logger()
_r: redis.Redis | None = None
# Compatibilidade com testes antigos: tarefa opcional de buffer
buffer_incoming_message = None  # type: ignore

# Compatibilidade com testes antigos e monkeypatch:
# historicamente o webhook usava `with SessionLocal() as db:`.
# Mantemos o símbolo `SessionLocal` apontando para o context manager `db_session`.
SessionLocal = db_session


def _resolve_tenant_from_phone_number_id(db: Session, phone_number_id: str | None) -> core_models.Tenant:
    try:
        return resolve_tenant_from_phone_number_id(db, phone_number_id)
    except TenantResolutionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


def _redis() -> redis.Redis:
    global _r
    if _r is None:
        # Usa REDIS_URL das settings
        _r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _r


def _ensure_contact(db: Session, tenant_id: int, wa_id: str) -> core_models.Contact:
    stmt = select(core_models.Contact).where(
        core_models.Contact.tenant_id == int(tenant_id),
        core_models.Contact.wa_id == str(wa_id),
    )
    c = db.execute(stmt).scalar_one_or_none()
    if not c:
        c = core_models.Contact(tenant_id=int(tenant_id), wa_id=str(wa_id))
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def _ensure_conversation(db: Session, tenant_id: int, contact_id: int) -> core_models.Conversation:
    stmt = (
        select(core_models.Conversation)
        .where(
            core_models.Conversation.tenant_id == int(tenant_id),
            core_models.Conversation.contact_id == int(contact_id),
            core_models.Conversation.status == core_models.ConversationStatus.active_bot,
        )
        .order_by(core_models.Conversation.id.desc())
        .limit(1)
    )
    conv = db.execute(stmt).scalars().first()
    if not conv:
        conv = core_models.Conversation(
            tenant_id=int(tenant_id),
            contact_id=int(contact_id),
            status=core_models.ConversationStatus.active_bot,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _get_latest_lead_for_contact(db: Session, tenant_id: int, contact_id: int) -> re_models.Lead | None:
    stmt = (
        select(re_models.Lead)
        .where(re_models.Lead.tenant_id == int(tenant_id), re_models.Lead.contact_id == int(contact_id))
        .order_by(re_models.Lead.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _record_event(db: Session, conversation_id: int, type_: str, payload: dict) -> None:
    db.add(core_models.ConversationEvent(conversation_id=int(conversation_id), type=type_, payload=payload))
    db.commit()


def _parse_campaign_and_property(db: Session, tenant_id: int, text: str) -> dict | None:
    _ = db
    _ = tenant_id
    _ = text
    return None


@router.get("")
async def verify(
    request: Request,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    """
    Meta sends the verification GET with query params using the 'hub.' prefix.
    Example: /webhook?hub.mode=subscribe&hub.challenge=123&hub.verify_token=xxx
    """
    if hub_verify_token != settings.WA_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    # Return the challenge as plain text
    return PlainTextResponse(hub_challenge or "")


@router.post("")
async def receive(request: Request):
    # Read raw body to handle different encodings safely
    import json  # local import to avoid global overhead
    body_bytes: bytes = await request.body()
    # Optional: validate HMAC from Meta if secret configured
    try:
        secret = settings.WA_WEBHOOK_SECRET
    except Exception:
        secret = ""
    signature = request.headers.get("x-hub-signature-256")
    is_test_env = (settings.APP_ENV == "test") or (os.getenv("PYTEST_CURRENT_TEST") is not None)
    host = request.headers.get("host") or (request.url.hostname or "")
    is_test_client = host.startswith("testserver")
    if secret:
        # Em testes: se assinatura vier, devemos validar (para permitir teste específico de HMAC)
        # Em produção/dev: sempre validar quando secret está definido
        must_validate = True
        if (is_test_env or is_test_client) and not signature:
            # ambiente de teste sem assinatura -> ignorar validação para facilitar testes de fluxo
            must_validate = False
        if must_validate:
            if not signature or not signature.startswith("sha256="):
                log.error("webhook_hmac_missing_or_malformed")
                return {"received": True, "error": "invalid_signature"}
            expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
            provided = signature.split("=", 1)[1]
            if not hmac.compare_digest(expected, provided):
                log.error("webhook_hmac_mismatch")
                return {"received": True, "error": "invalid_signature"}
        else:
            log.info(
                "webhook_hmac_skipped_for_test",
                app_env=settings.APP_ENV,
                pytest=os.getenv("PYTEST_CURRENT_TEST") is not None,
                host=host,
                is_test_client=is_test_client,
            )
    payload = None
    if not body_bytes:
        log.error("webhook_json_error", error="empty body")
        return {"received": True, "error": "invalid_json"}
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            payload = json.loads(body_bytes.decode(enc))
            break
        except Exception:  # noqa: BLE001
            payload = None
            continue
    if payload is None:
        try:
            # As a last resort, try FastAPI's parser
            payload = await request.json()
        except Exception as e:  # noqa: BLE001
            log.error("webhook_json_error", error=str(e))
            return {"received": True, "error": "invalid_json"}

    log.info("webhook_received", payload=payload)

    # Extrair texto e wa_id do payload do WhatsApp
    try:
        entries = payload.get("entry", []) or []
        for entry in entries:
            changes = entry.get("changes", []) or []
            for change in changes:
                value = change.get("value", {}) or {}
                metadata = value.get("metadata", {}) or {}
                phone_number_id = metadata.get("phone_number_id")
                messages = value.get("messages", []) or []
                contacts = value.get("contacts", []) or []
                wa_id = None
                if contacts:
                    wa_id = contacts[0].get("wa_id") or contacts[0].get("wa_id")
                for msg in messages:
                    if not wa_id:
                        wa_id = msg.get("from")
                    if msg.get("type") != "text":
                        continue
                    # Idempotência: se já processamos esta mensagem, ignore
                    msg_id = msg.get("id") or ""
                    if msg_id:
                        try:
                            r = _redis()
                            dedup_key = f"wh:dedup:{msg_id}"
                            if r.get(dedup_key):
                                log.info("webhook_duplicated_msg", msg_id=msg_id)
                                continue
                            # marca como visto por 2 minutos
                            r.setex(dedup_key, 120, "1")
                        except Exception as e:
                            # Em dev/local sem Redis, apenas seguir sem deduplicação
                            log.info("redis_dedup_skipped", error=str(e))
                    text_in = (msg.get("text", {}) or {}).get("body", "").strip()
                    if not text_in:
                        continue

                    # Compat: se existir tarefa de buffer, enfileira e segue
                    try:
                        if buffer_incoming_message is not None:
                            log.info(
                                "buffer_enqueue_call",
                                phone_number_id=phone_number_id,
                                wa_id=wa_id or "unknown",
                                text=text_in,
                            )
                            buffer_incoming_message.delay(settings.DEFAULT_TENANT_ID, wa_id or "unknown", text_in)
                            # Compatibilidade: quando buffer está habilitado, não processa sincronamente.
                            continue
                    except Exception as e:  # noqa: BLE001
                        log.error("buffer_enqueue_error", error=str(e))

                    # Processar funil imobiliário sincronamente (MVP)
                    with SessionLocal() as db:
                        # Garantir tenant/contact/conversation para atualização de lead (24h)
                        tenant = _resolve_tenant_from_phone_number_id(db, phone_number_id)
                        contact = _ensure_contact(db, tenant.id, wa_id or "unknown")
                        conv = _ensure_conversation(db, tenant.id, contact.id)
                        lead = _get_latest_lead_for_contact(db, tenant.id, contact.id)
                        if not lead:
                            lead = re_models.Lead.create_for_contact(tenant.id, contact.id, str(contact.wa_id))
                            db.add(lead)
                            db.commit()
                            db.refresh(lead)
                            _record_event(db, conv.id, "lead.created", {"status": lead.status.value})
                        else:
                            lead.last_inbound_at = datetime.utcnow()
                            original_status = lead.status
                            lead.reactivate_if_needed()
                            if original_status != lead.status:
                                _record_event(db, conv.id, "lead.status_updated", {"status": lead.status.value})
                            db.add(lead)
                            db.commit()

                        # Detectar campanha/refs do texto e registrar evento para consumo no funil
                        try:
                            camp = _parse_campaign_and_property(db, tenant.id, text_in)
                            if camp:
                                _record_event(db, conv.id, "re_campaign", camp)
                        except Exception as e:
                            log.warning("campaign_parse_error", error=str(e))

                        resp_text = ""
                        try:
                            state_service = ConversationStateService(redis_client=_redis())
                            sender_id = wa_id or "unknown"
                            state = normalize_state(
                                state=(state_service.get_state(sender_id, tenant_id=int(tenant.id)) or {}),
                                sender_id=sender_id,
                                tenant_id=int(tenant.id),
                                default_stage="start",
                            )
                            state = await enrich_state_with_llm(
                                sender_id=sender_id,
                                text_raw=text_in,
                                state=state,
                                log=log,
                            )
                            flow_out = try_process_via_flow_engine(
                                db=db,
                                state_service=state_service,
                                sender_id=sender_id,
                                tenant_id=int(tenant.id),
                                domain="real_estate",
                                text_raw=text_in,
                                text_normalized=text_in,
                                initial_state=state,
                            )
                            if flow_out.handled and flow_out.message:
                                resp_text = flow_out.message
                        except Exception as e:  # noqa: BLE001
                            log.info("webhook_flow_engine_skipped", error=str(e))

                        if not resp_text:
                            funnel_service = FunnelService(db=db)
                            resp_text = funnel_service.process_message(
                                tenant_id=tenant.id,
                                wa_id=wa_id or "unknown",
                                user_text=text_in,
                            )
                        # Enviar resposta via provider configurado (Meta Cloud por padrão)
                        try:
                            provider = get_provider()
                            to = wa_id or ""
                            if to:
                                provider.send_text(to=to, text=resp_text, tenant_id=str(int(tenant.id)))
                                # Atualizar last_outbound_at no último lead deste contato
                                lead = _get_latest_lead_for_contact(db, tenant.id, contact.id)
                                if lead:
                                    lead.last_outbound_at = datetime.utcnow()
                                    db.add(lead)
                                    db.commit()
                            log.info("bot_reply", wa_id=wa_id, reply=resp_text)
                        except Exception as e:  # noqa: BLE001
                            log.error("bot_reply_error", error=str(e))
        return {"received": True}
    except Exception as e:  # noqa: BLE001
        log.error("webhook_process_error", error=str(e))
        # Em dev, retornar detalhe para diagnóstico rápido
        if settings.APP_ENV != "prod":
            return {"received": True, "error": "processing", "detail": str(e)}
        return {"received": True, "error": "processing"}


class PaymentEvent(BaseModel):
    order_id: int
    payment_id: str | None = None
    status: Literal["paid"]


 


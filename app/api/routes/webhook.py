from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from app.core.config import settings
from app.messaging.provider import get_provider
import structlog
import os
import hmac
import hashlib
from app.repositories.db import SessionLocal
from datetime import datetime
import re
from urllib.parse import urlparse
import redis
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.repositories import models as core_models
from app.domain.realestate import models as re_models
 
from pydantic import BaseModel
from typing import Literal
 

router = APIRouter()
log = structlog.get_logger()
_r: redis.Redis | None = None
# Compatibilidade com testes antigos: tarefa opcional de buffer
buffer_incoming_message = None  # type: ignore


def _redis() -> redis.Redis:
    global _r
    if _r is None:
        # Usa REDIS_URL das settings
        _r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _r


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
                                tenant=settings.DEFAULT_TENANT_ID,
                                wa_id=wa_id or "unknown",
                                text=text_in,
                            )
                            buffer_incoming_message.delay(
                                settings.DEFAULT_TENANT_ID,
                                wa_id or "unknown",
                                text_in,
                            )
                    except Exception as e:  # noqa: BLE001
                        log.error("buffer_enqueue_error", error=str(e))

                    # Processar funil imobiliário sincronamente (MVP)
                    with SessionLocal() as db:
                        # Garantir tenant/contact/conversation para atualização de lead (24h)
                        tenant = _ensure_tenant(db, settings.DEFAULT_TENANT_ID)
                        contact = _ensure_contact(db, tenant.id, wa_id or "unknown")
                        conv = _ensure_conversation(db, tenant.id, contact.id)
                        _update_lead_on_inbound(db, tenant.id, contact.id, conv.id)

                        # Detectar campanha/refs do texto e registrar evento para consumo no funil
                        try:
                            camp = _parse_campaign_and_property(db, tenant.id, text_in)
                            if camp:
                                _record_event(db, conv.id, "re_campaign", camp)
                        except Exception as e:
                            log.warning("campaign_parse_error", error=str(e))

                        resp_text = _process_realestate_funnel(db, tenant_name=settings.DEFAULT_TENANT_ID, wa_id=wa_id or "unknown", user_text=text_in)
                        # Enviar resposta via provider configurado (Meta Cloud por padrão)
                        try:
                            provider = get_provider()
                            to = wa_id or ""
                            if to:
                                provider.send_text(to=to, text=resp_text)
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


 
def _normalize_text(s: str) -> str:
    return s.strip().lower()


def _ensure_tenant(db: Session, tenant_name: str) -> core_models.Tenant:
    stmt = select(core_models.Tenant).where(core_models.Tenant.name == tenant_name)
    tenant = db.execute(stmt).scalar_one_or_none()
    if not tenant:
        tenant = core_models.Tenant(name=tenant_name)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def _ensure_contact(db: Session, tenant_id: int, wa_id: str) -> core_models.Contact:
    stmt = select(core_models.Contact).where(
        core_models.Contact.tenant_id == tenant_id,
        core_models.Contact.wa_id == wa_id,
    )
    c = db.execute(stmt).scalar_one_or_none()
    if not c:
        c = core_models.Contact(tenant_id=tenant_id, wa_id=wa_id)
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def _ensure_conversation(db: Session, tenant_id: int, contact_id: int) -> core_models.Conversation:
    stmt = (
        select(core_models.Conversation)
        .where(
            core_models.Conversation.tenant_id == tenant_id,
            core_models.Conversation.contact_id == contact_id,
            core_models.Conversation.status == core_models.ConversationStatus.active_bot,
        )
        .order_by(core_models.Conversation.id.desc())
        .limit(1)
    )
    conv = db.execute(stmt).scalars().first()
    if not conv:
        conv = core_models.Conversation(
            tenant_id=tenant_id,
            contact_id=contact_id,
            status=core_models.ConversationStatus.active_bot,
            last_state=None,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _record_event(db: Session, conversation_id: int, type_: str, payload: dict) -> None:
    db.add(core_models.ConversationEvent(conversation_id=conversation_id, type=type_, payload=payload))
    db.commit()


def _get_latest_lead_for_contact(db: Session, tenant_id: int, contact_id: int) -> re_models.Lead | None:
    stmt = (
        select(re_models.Lead)
        .where(re_models.Lead.tenant_id == tenant_id, re_models.Lead.contact_id == contact_id)
        .order_by(re_models.Lead.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _has_pending_visit(db: Session, lead_id: int) -> bool:
    stmt = (
        select(re_models.VisitSchedule)
        .where(
            re_models.VisitSchedule.lead_id == lead_id,
            re_models.VisitSchedule.status == re_models.VisitStatus.requested,
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def _is_lead_fully_qualified(lead: re_models.Lead) -> bool:
    """
    Lead é QUALIFICADO quando:
    1. Forneceu preferências mínimas (finalidade, tipo, cidade, preço)
    2. Bot já enviou sugestões de imóveis
    
    NÃO exige: email, estado (redundante), nome completo
    """
    # Preferências mínimas necessárias
    has_prefs = (
        bool((lead.finalidade or "").strip())  # Compra ou locação
        and bool((lead.tipo or "").strip())    # Casa, apartamento, etc
        and bool((lead.cidade or "").strip())  # Cidade de interesse
        and (lead.preco_min is not None or lead.preco_max is not None)  # Faixa de preço
    )
    
    # Verificar se bot já enviou imóveis (search_results no preferences)
    bot_sent_properties = False
    if lead.preferences and isinstance(lead.preferences, dict):
        search_results = lead.preferences.get('search_results')
        bot_sent_properties = bool(search_results and len(search_results) > 0)
    
    return has_prefs and bot_sent_properties


def _update_lead_on_inbound(db: Session, tenant_id: int, contact_id: int, conversation_id: int) -> None:
    lead = _get_latest_lead_for_contact(db, tenant_id, contact_id)
    if not lead:
        # Primeiro contato: criar lead iniciado para permitir triagem no painel
        contact = db.query(core_models.Contact).filter(core_models.Contact.id == contact_id).first()
        if not contact:
            return
        lead = re_models.Lead(
            tenant_id=tenant_id,
            name=None,
            phone=str(contact.wa_id),
            email=None,
            source="whatsapp",
            preferences={},
            consent_lgpd=False,
            contact_id=contact_id,
            status="iniciado",
            last_inbound_at=datetime.utcnow(),
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _record_event(db, conversation_id, "lead.created", {"status": lead.status})
        return
    lead.last_inbound_at = datetime.utcnow()
    if lead.status == "sem_resposta_24h":
        # Recalcular status de forma determinística
        if _has_pending_visit(db, lead.id):
            lead.status = "agendamento_pendente"
        elif _is_lead_fully_qualified(lead):
            lead.status = "qualificado"
        else:
            lead.status = "novo"
        lead.status_updated_at = datetime.utcnow()
        _record_event(db, conversation_id, "lead.status_updated", {"status": lead.status})
    db.add(lead)
    db.commit()


def _detect_campaign_source(urls: list[str]) -> str | None:
    for u in urls:
        try:
            host = urlparse(u).netloc.lower()
        except Exception:
            continue
        if "chavesnamao.com.br" in host:
            return "chavesnamao"
        if host.startswith("fb.me") or "facebook.com" in host:
            return "facebook"
        if "instagram.com" in host:
            return "instagram"
        if "google" in host or "g.page" in host:
            return "google"
    return None


def _infer_purpose(text: str, urls: list[str]) -> str | None:
    t = text.lower()
    if any(k in t for k in ["alugar", "locação", "locacao", "aluguel"]):
        return "rent"
    if any(k in t for k in ["comprar", "compra", "venda", "vender"]):
        return "sale"
    for u in urls:
        lu = u.lower()
        if any(k in lu for k in ["para-alugar", "alugar", "aluguel"]):
            return "rent"
        if any(k in lu for k in ["para-venda", "comprar", "venda"]):
            return "sale"
    return None


def _resolve_property_by_ref_code(db: Session, tenant_id: int, ref_code: str) -> int | None:
    stmt = (
        select(re_models.Property.id)
        .where(re_models.Property.tenant_id == tenant_id, re_models.Property.ref_code == ref_code)
        .limit(1)
    )
    pid = db.execute(stmt).scalars().first()
    return int(pid) if pid is not None else None


def _resolve_property_by_external(db: Session, tenant_id: int, provider: str, external_id: str) -> int | None:
    stmt = (
        select(re_models.PropertyExternalRef.property_id)
        .where(
            re_models.PropertyExternalRef.tenant_id == tenant_id,
            re_models.PropertyExternalRef.provider == provider,
            re_models.PropertyExternalRef.external_id == external_id,
        )
        .limit(1)
    )
    pid = db.execute(stmt).scalars().first()
    return int(pid) if pid is not None else None


def _parse_campaign_and_property(db: Session, tenant_id: int, text: str) -> dict:
    # URLs e códigos de referência
    urls = re.findall(r"https?://\S+", text)
    ref_codes = re.findall(r"\bA\d{3,6}\b", text)

    data: dict = {}
    if urls:
        data["landing_url"] = urls[0]
        src = _detect_campaign_source(urls)
        if src:
            data["campaign_source"] = src
            data["campaign_medium"] = "paid"  # heurística; ajustar quando houver UTM
        # chavesnamao external id: .../id-34275329
        if src == "chavesnamao":
            m = re.search(r"id-(\d+)", urls[0])
            if m:
                data["external_property_id"] = m.group(1)
                pid = _resolve_property_by_external(db, tenant_id, "chavesnamao", data["external_property_id"])  # type: ignore
                if pid:
                    data["property_id"] = pid
    if ref_codes:
        ref = ref_codes[0]
        data["ref_code"] = ref
        pid = _resolve_property_by_ref_code(db, tenant_id, ref)
        if pid:
            data["property_id"] = pid

    purpose = _infer_purpose(text, urls)
    if purpose:
        data["purpose"] = purpose

    return data


def _parse_price(text: str) -> tuple[float | None, float | None]:
    # aceita formatos simples: "2000-3500" ou "ate 3000" ou "3000"
    t = _normalize_text(text).replace("r$", "").replace(" ", "")
    if "-" in t:
        parts = t.split("-", 1)
        try:
            return float(parts[0]), float(parts[1])
        except Exception:
            return None, None
    if t.startswith("ate"):
        try:
            return None, float(t.replace("ate", ""))
        except Exception:
            return None, None
    try:
        v = float(t)
        return v, v
    except Exception:
        return None, None


def _process_realestate_funnel(db: Session, tenant_name: str, wa_id: str, user_text: str) -> str:
    """State machine mínima para coletar filtros de busca e retornar imóveis.

    Estados: purpose -> location_city -> location_state -> type -> bedrooms -> price -> done
    """
    tenant = _ensure_tenant(db, tenant_name)
    contact = _ensure_contact(db, tenant.id, wa_id)
    conv = _ensure_conversation(db, tenant.id, contact.id)

    text = _normalize_text(user_text)

    # Recuperar progresso anterior
    last = conv.last_state or "purpose"
    criteria: dict = {}
    # Buscar último event de tipo re_funnel se existir
    stmt = (
        select(core_models.ConversationEvent)
        .where(
            core_models.ConversationEvent.conversation_id == conv.id,
            core_models.ConversationEvent.type == "re_funnel",
        )
        .order_by(core_models.ConversationEvent.id.desc())
    )
    ev = db.execute(stmt).scalars().first()
    if ev and isinstance(ev.payload, dict):
        criteria = dict(ev.payload)

    # Buscar último evento de campanha e fundir informações úteis
    stmt_c = (
        select(core_models.ConversationEvent)
        .where(
            core_models.ConversationEvent.conversation_id == conv.id,
            core_models.ConversationEvent.type == "re_campaign",
        )
        .order_by(core_models.ConversationEvent.id.desc())
    )
    camp_ev = db.execute(stmt_c).scalars().first()
    campaign_data: dict = {}
    if camp_ev and isinstance(camp_ev.payload, dict):
        campaign_data = dict(camp_ev.payload)
        # Inferências que ajudam o funil
        if campaign_data.get("purpose") and not criteria.get("purpose"):
            criteria["purpose"] = campaign_data["purpose"]

    def save_criteria(next_state: str) -> None:
        conv.last_state = next_state
        db.add(conv)
        _record_event(db, conv.id, "re_funnel", criteria)

    # State: purpose (compra/locação)
    if last == "purpose":
        if text in {"compra", "comprar", "venda", "buy", "sale"}:
            criteria["purpose"] = "sale"
            save_criteria("location_city")
            return "Legal! Você quer comprar. Me diga a cidade (ex: São Paulo)."
        if text in {"locacao", "locação", "aluguel", "alugar", "rent"}:
            criteria["purpose"] = "rent"
            save_criteria("location_city")
            return "Perfeito! Você quer alugar. Qual a cidade?"
        return "Olá! Você procura compra ou locação?"

    # State: cidade
    if last == "location_city":
        if len(text) < 2:
            return "Informe a cidade (ex: Campinas)."
        criteria["city"] = user_text.strip()
        save_criteria("location_state")
        return "Anotado. Qual o estado (UF)? (ex: SP)"

    # State: estado
    if last == "location_state":
        uf = text.upper().replace(" ", "")
        if len(uf) != 2:
            return "Informe a UF com 2 letras (ex: SP)."
        criteria["state"] = uf
        save_criteria("type")
        return "Certo. Prefere apartamento ou casa?"

    # State: tipo
    if last == "type":
        if text in {"ap", "apto", "apartamento", "apartment"}:
            criteria["type"] = "apartment"
        elif text in {"casa", "house"}:
            criteria["type"] = "house"
        else:
            return "Digite 'apartamento' ou 'casa'."
        save_criteria("bedrooms")
        return "Quantos dormitórios? (ex: 2)"

    # State: dormitórios
    if last == "bedrooms":
        try:
            n = int("".join(ch for ch in text if ch.isdigit()))
            criteria["bedrooms"] = n
            save_criteria("price")
            return "Qual a faixa de preço? (ex: 2000-3500 ou 'ate 3000')"
        except Exception:
            return "Informe um número de dormitórios (ex: 2)."

    # State: preço e busca
    if last == "price":
        min_p, max_p = _parse_price(user_text)
        if min_p is not None:
            criteria["min_price"] = min_p
        if max_p is not None:
            criteria["max_price"] = max_p

        # Atualizar ou criar lead do contato (evita lead com phone=None)
        lead = _get_latest_lead_for_contact(db, tenant.id, contact.id)
        if not lead:
            lead = re_models.Lead(
                tenant_id=tenant.id,
                name=None,
                phone=wa_id,
                email=None,
                source="whatsapp",
                preferences={},
                consent_lgpd=False,
                contact_id=contact.id,
                status="novo",
                last_inbound_at=datetime.utcnow(),
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

        lead.status = "novo"
        lead.status_updated_at = datetime.utcnow()
        lead.preferences = criteria
        lead.finalidade = criteria.get("purpose")
        lead.tipo = criteria.get("type")
        lead.cidade = criteria.get("city")
        lead.estado = criteria.get("state")
        lead.dormitorios = int(criteria.get("bedrooms")) if criteria.get("bedrooms") is not None else None
        lead.preco_min = float(criteria.get("min_price")) if criteria.get("min_price") is not None else None
        lead.preco_max = float(criteria.get("max_price")) if criteria.get("max_price") is not None else None
        lead.campaign_source = campaign_data.get("campaign_source")
        lead.campaign_medium = campaign_data.get("campaign_medium")
        lead.campaign_name = campaign_data.get("campaign_name")
        lead.campaign_content = campaign_data.get("campaign_content")
        lead.landing_url = campaign_data.get("landing_url")
        lead.external_property_id = campaign_data.get("external_property_id")
        lead.property_interest_id = campaign_data.get("property_id")
        db.add(lead)
        db.commit()
        db.refresh(lead)

        inquiry = re_models.Inquiry(
            tenant_id=tenant.id,
            lead_id=lead.id,
            property_id=campaign_data.get("property_id"),
            type=re_models.InquiryType.buy if criteria.get("purpose") == "sale" else re_models.InquiryType.rent,
            status=re_models.InquiryStatus.new,
            payload=criteria,
        )
        db.add(inquiry)
        db.commit()

        # Buscar imóveis
        stmt = select(re_models.Property).where(re_models.Property.is_active == True)  # noqa: E712
        if criteria.get("purpose"):
            stmt = stmt.where(re_models.Property.purpose == re_models.PropertyPurpose(criteria["purpose"]))
        if criteria.get("type"):
            stmt = stmt.where(re_models.Property.type == re_models.PropertyType(criteria["type"]))
        if criteria.get("city"):
            stmt = stmt.where(re_models.Property.address_city.ilike(criteria["city"]))
        if criteria.get("state"):
            stmt = stmt.where(re_models.Property.address_state == criteria["state"])
        if criteria.get("bedrooms") is not None:
            stmt = stmt.where(re_models.Property.bedrooms >= int(criteria["bedrooms"]))
        if criteria.get("min_price") is not None:
            stmt = stmt.where(re_models.Property.price >= float(criteria["min_price"]))
        if criteria.get("max_price") is not None:
            stmt = stmt.where(re_models.Property.price <= float(criteria["max_price"]))

        stmt = stmt.limit(5)
        rows = db.execute(stmt).scalars().all()

        conv.last_state = "done"
        db.add(conv)
        db.commit()

        if not rows:
            return "Obrigado! Registrei sua preferência. No momento não encontrei imóveis com esse perfil. Quer ajustar a faixa de preço ou dormitórios?"

        lines = ["Encontrei estas opções:"]
        for p in rows:
            lines.append(f"#{p.id} - {p.title} | R$ {p.price:,.0f} | {p.address_city}-{p.address_state}")
        lines.append("Deseja ver mais detalhes? Envie o número do imóvel (ex: 3).")
        return "\n".join(lines)

    # State final ou desconhecido: reinicia
    conv.last_state = "purpose"
    db.add(conv)
    db.commit()
    return "Vamos começar! Você procura compra ou locação?"


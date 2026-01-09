from __future__ import annotations
import httpx
from typing import Optional, Dict, Any, List
import time

from app.messaging.limits import RateLimiter
from app.repositories.db import db_session
from app.repositories.models import (
    SuppressedContact,
    MessageLog,
    Contact,
    Conversation,
    Message,
    MessageDirection,
    WhatsAppAccount,
)
from app.core.config import settings


class MetaCloudProvider:
    def __init__(self, api_base: str, token: str, phone_number_id: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.phone_number_id = phone_number_id
        self._client = httpx.Client(timeout=15.0)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _messages_url(self, phone_number_id: str) -> str:
        return f"{self.api_base}/{phone_number_id}/messages"

    def _resolve_credentials(self, tenant_id: Optional[str]) -> tuple[str, str]:
        """Resolve (token, phone_number_id) for a given tenant.

        Falls back to global settings when tenant is not provided or no account exists.
        """
        token = self.token
        phone_number_id = self.phone_number_id
        if not tenant_id:
            return token, phone_number_id
        try:
            tid = int(tenant_id)
        except Exception:
            return token, phone_number_id

        try:
            with db_session() as db:
                acct = (
                    db.query(WhatsAppAccount)
                    .filter(
                        WhatsAppAccount.tenant_id == tid,
                        WhatsAppAccount.is_active == True,  # noqa: E712
                    )
                    .order_by(WhatsAppAccount.id.desc())
                    .first()
                )
                if acct:
                    if acct.token:
                        token = acct.token
                    if acct.phone_number_id:
                        phone_number_id = acct.phone_number_id
        except Exception:
            # Fail closed on credential override issues: keep default settings
            pass
        return token, phone_number_id

    def _post_with_retry(self, url: str, json: Dict[str, Any], max_attempts: int = 3) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                r = self._client.post(url, headers=self._headers(), json=json)
                r.raise_for_status()
                return r
            except Exception as exc:
                last_exc = exc
                # Backoff exponencial curto: 0.3s, 0.6s
                if attempt < max_attempts:
                    time.sleep(0.3 * (2 ** (attempt - 1)))
        # Se esgotou tentativas, relança a última exceção
        assert last_exc is not None
        raise last_exc

    def send_text(self, to: str, text: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        tenant = tenant_id or "0"
        token, phone_number_id = self._resolve_credentials(tenant_id)
        # Rate limit & supressão
        limiter = RateLimiter(
            tenant,
            por_contato_interval_s=settings.WA_RATE_LIMIT_PER_CONTACT_SECONDS,
            global_per_minute=settings.WA_RATE_LIMIT_GLOBAL_PER_MINUTE,
        )
        if not limiter.allow(to):
            raise RuntimeError("rate_limited_or_global_limit")
        with db_session() as db:
            # Guard da janela 24h (somente para texto livre)
            if settings.WINDOW_24H_ENABLED:
                contact = (
                    db.query(Contact)
                    .filter(Contact.tenant_id == int(tenant), Contact.wa_id == to)
                    .first()
                )
                inside = False
                if contact:
                    # última inbound do cliente em qualquer conversa do contato
                    last_inbound = (
                        db.query(Message)
                        .filter(
                            Message.tenant_id == int(tenant),
                            Message.direction == MessageDirection.inbound,
                            Message.conversation_id.in_(
                                db.query(Conversation.id).filter(Conversation.contact_id == contact.id)
                            ),
                        )
                        .order_by(Message.created_at.desc())
                        .first()
                    )
                    if last_inbound is not None:
                        from datetime import datetime, timedelta, timezone

                        now = datetime.now(timezone.utc)
                        # normalizar created_at como naive->utc se necessário
                        li = last_inbound.created_at
                        if li.tzinfo is None:
                            li = li.replace(tzinfo=timezone.utc)
                        inside = (now - li) <= timedelta(hours=settings.WINDOW_24H_HOURS)
                if not inside:
                    raise RuntimeError("outside_session_window")
            sup = db.query(SuppressedContact).filter(
                SuppressedContact.tenant_id == int(tenant),
                SuppressedContact.wa_id == to,
            ).first()
            if sup:
                raise RuntimeError("suppressed_contact")
            log = MessageLog(tenant_id=int(tenant), to=to, kind="text", body={"body": text[:4096]}, status="queued")
            db.add(log)
            db.commit()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text[:4096]},
        }
        try:
            url = f"{self.api_base}/{phone_number_id}/messages"
            prev = self.token
            try:
                self.token = token
                r = self._post_with_retry(url, payload)
            finally:
                self.token = prev
            data = r.json()
            provider_id = None
            try:
                provider_id = data.get("messages", [{}])[0].get("id")
            except Exception:
                provider_id = None
            with db_session() as db:
                last = (
                    db.query(MessageLog)
                    .filter(
                        MessageLog.tenant_id == int(tenant),
                        MessageLog.to == to,
                        MessageLog.kind == "text",
                    )
                    .order_by(MessageLog.id.desc())
                    .first()
                )
                if last:
                    last.status = "sent"
                    last.provider_message_id = provider_id
                    db.add(last)
                    db.commit()
            return data
        except Exception as exc:
            with db_session() as db:
                last = (
                    db.query(MessageLog)
                    .filter(
                        MessageLog.tenant_id == int(tenant),
                        MessageLog.to == to,
                        MessageLog.kind == "text",
                    )
                    .order_by(MessageLog.id.desc())
                    .first()
                )
                if last:
                    last.status = "error"
                    last.error_code = str(exc)
                    db.add(last)
                    db.commit()
            raise

    def send_template(
        self,
        to: str,
        template_name: str,
        language: str = "pt_BR",
        components: Optional[List[Dict[str, Any]]] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tenant = tenant_id or "0"
        token, phone_number_id = self._resolve_credentials(tenant_id)
        limiter = RateLimiter(
            tenant,
            por_contato_interval_s=settings.WA_RATE_LIMIT_PER_CONTACT_SECONDS,
            global_per_minute=settings.WA_RATE_LIMIT_GLOBAL_PER_MINUTE,
        )
        if not limiter.allow(to):
            raise RuntimeError("rate_limited_or_global_limit")
        with db_session() as db:
            sup = db.query(SuppressedContact).filter(
                SuppressedContact.tenant_id == int(tenant),
                SuppressedContact.wa_id == to,
            ).first()
            if sup:
                raise RuntimeError("suppressed_contact")
            log = MessageLog(
                tenant_id=int(tenant),
                to=to,
                kind="template",
                body={"components": components or []},
                template_name=template_name,
                status="queued",
            )
            db.add(log)
            db.commit()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        if components:
            payload["template"]["components"] = components
        try:
            url = f"{self.api_base}/{phone_number_id}/messages"
            # Temporarily override token for this request
            prev = self.token
            try:
                self.token = token
                r = self._post_with_retry(url, payload)
            finally:
                self.token = prev
            data = r.json()
            provider_id = None
            try:
                provider_id = data.get("messages", [{}])[0].get("id")
            except Exception:
                provider_id = None
            with db_session() as db:
                last = (
                    db.query(MessageLog)
                    .filter(
                        MessageLog.tenant_id == int(tenant),
                        MessageLog.to == to,
                        MessageLog.kind == "template",
                    )
                    .order_by(MessageLog.id.desc())
                    .first()
                )
                if last:
                    last.status = "sent"
                    last.provider_message_id = provider_id
                    db.add(last)
                    db.commit()
            return data
        except Exception as exc:
            with db_session() as db:
                last = (
                    db.query(MessageLog)
                    .filter(
                        MessageLog.tenant_id == int(tenant),
                        MessageLog.to == to,
                        MessageLog.kind == "template",
                    )
                    .order_by(MessageLog.id.desc())
                    .first()
                )
                if last:
                    last.status = "error"
                    last.error_code = str(exc)
                    db.add(last)
                    db.commit()
            raise

    def mark_read(self, message_id: str) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        r = self._post_with_retry(f"{self.api_base}/{self.phone_number_id}/messages", payload)
        return r.json()

"""
Serviço para envio de notificações (email, WhatsApp, etc).
"""
from typing import Optional
import structlog

from sqlalchemy.orm import Session

from app.domain.realestate import models as re_models
from app.messaging.provider import get_provider
from app.repositories.models import Tenant

log = structlog.get_logger()


class NotificationService:
    """Serviço para enviar notificações sobre agendamentos."""

    @staticmethod
    def _normalize_wa_id(raw: str) -> str:
        s = (raw or "").strip()
        if not s:
            return s
        if "@" in s:
            s = s.split("@", 1)[0]
        if s.startswith("+"):
            s = s[1:]
        s = "".join(ch for ch in s if ch.isdigit())
        return s

    @staticmethod
    def _get_recipients(settings_json: dict) -> list[str]:
        raw = settings_json.get("booking_notification_recipients")
        if not raw:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw if str(x).strip()]
        return []

    @staticmethod
    def _get_template_name(settings_json: dict) -> str | None:
        name = (settings_json.get("booking_notification_template") or "").strip()
        return name or None

    @staticmethod
    def _format_visit_requested_message(visit: re_models.VisitSchedule, lead: re_models.Lead | None, prop: re_models.Property | None) -> str:
        lead_name = (getattr(lead, "name", None) or "-")
        lead_phone = (getattr(lead, "phone", None) or getattr(visit, "contact_phone", None) or "-")
        ref = ""
        if prop is not None:
            ref = getattr(prop, "ref_code", None) or getattr(prop, "external_id", None) or str(getattr(prop, "id", ""))
        dt = getattr(visit, "scheduled_datetime", None)
        dt_txt = dt.strftime("%d/%m/%Y %H:%M") if dt else "-"
        return (
            "📅 *Solicitação de visita (pendente de confirmação)*\n"
            f"• Lead: {lead_name}\n"
            f"• Contato: {lead_phone}\n"
            f"• Imóvel: #{ref}\n"
            f"• Sugestão: {dt_txt}"
        )

    @staticmethod
    def notify_visit_requested(db: Session, visit_id: int) -> dict:
        visit = db.get(re_models.VisitSchedule, int(visit_id))
        if not visit:
            return {"notified": 0, "errors": [{"error": "visit_not_found"}]}

        tenant = db.get(Tenant, int(getattr(visit, "tenant_id", 0)))
        if not tenant:
            return {"notified": 0, "errors": [{"error": "tenant_not_found"}]}

        settings_json = dict(getattr(tenant, "settings_json", {}) or {})
        recipients = NotificationService._get_recipients(settings_json)
        template_name = NotificationService._get_template_name(settings_json)

        lead = db.get(re_models.Lead, int(getattr(visit, "lead_id"))) if getattr(visit, "lead_id", None) else None
        prop = db.get(re_models.Property, int(getattr(visit, "property_id"))) if getattr(visit, "property_id", None) else None
        text = NotificationService._format_visit_requested_message(visit, lead, prop)

        provider = get_provider()
        notified = 0
        errors: list[dict] = []

        for raw in recipients:
            to = NotificationService._normalize_wa_id(raw)
            if not to:
                continue
            try:
                if template_name:
                    provider.send_template(to, template_name, tenant_id=str(tenant.id))
                else:
                    provider.send_text(to, text, tenant_id=str(tenant.id))
                notified += 1
            except Exception as e:
                errors.append({"to": raw, "error": str(e)})

        log.info(
            "visit_requested_notification",
            visit_id=int(getattr(visit, "id", 0) or 0),
            recipients=len(recipients),
            notified=notified,
            errors=errors[:3],
        )
        return {"notified": notified, "errors": errors}
    
    @staticmethod
    def notify_visit_scheduled(
        visit_id: int,
        property_id: int,
        lead_name: str,
        phone: str,
        visit_datetime: str,
        property_address: Optional[str] = None
    ) -> bool:
        """
        Notifica equipe sobre novo agendamento de visita.
        
        Args:
            visit_id: ID do agendamento
            property_id: ID do imóvel
            lead_name: Nome do lead
            phone: Telefone de contato
            visit_datetime: Data/hora da visita
            property_address: Endereço do imóvel (opcional)
            
        Returns:
            True se notificação enviada com sucesso
        """
        # TODO: Implementar integração com sistema de notificações
        # Por enquanto, apenas log
        log.info(
            "visit_scheduled_notification",
            visit_id=visit_id,
            property_id=property_id,
            lead_name=lead_name,
            phone=phone,
            visit_datetime=visit_datetime,
            property_address=property_address
        )
        
        # Simular envio bem-sucedido
        return True
    
    @staticmethod
    def notify_visit_confirmed(visit_id: int, lead_name: str, phone: str) -> bool:
        """Notifica sobre confirmação de visita."""
        log.info(
            "visit_confirmed_notification",
            visit_id=visit_id,
            lead_name=lead_name,
            phone=phone
        )
        return True
    
    @staticmethod
    def notify_visit_cancelled(visit_id: int, lead_name: str, reason: Optional[str] = None) -> bool:
        """Notifica sobre cancelamento de visita."""
        log.info(
            "visit_cancelled_notification",
            visit_id=visit_id,
            lead_name=lead_name,
            reason=reason
        )
        return True
    
    @staticmethod
    def send_email(to: str, subject: str, body: str) -> bool:
        """
        Envia email (placeholder para implementação futura).
        
        Args:
            to: Destinatário
            subject: Assunto
            body: Corpo do email
            
        Returns:
            True se enviado com sucesso
        """
        log.info("email_sent", to=to, subject=subject)
        return True
    
    @staticmethod
    def send_whatsapp(phone: str, message: str) -> bool:
        """
        Envia mensagem WhatsApp (placeholder para implementação futura).
        
        Args:
            phone: Número do telefone
            message: Mensagem a enviar
            
        Returns:
            True se enviado com sucesso
        """
        log.info("whatsapp_sent", phone=phone, message_preview=message[:50])
        return True

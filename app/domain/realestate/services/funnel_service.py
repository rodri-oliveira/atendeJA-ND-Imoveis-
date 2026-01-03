from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.repositories import models as core_models
from app.domain.realestate import models as re_models
import re
from urllib.parse import urlparse
from datetime import datetime

# Funções movidas de webhook.py para este serviço de domínio

class FunnelService:
    def __init__(self, db: Session):
        self.db = db

    def process_message(self, tenant_id: int, wa_id: str, user_text: str) -> str:
        tenant = self._ensure_tenant(tenant_id)
        contact = self._ensure_contact(tenant.id, wa_id)
        conv = self._ensure_conversation(tenant.id, contact.id)

        text = self._normalize_text(user_text)

        last = conv.last_state or "purpose"
        criteria: dict = {}
        stmt = (
            select(core_models.ConversationEvent)
            .where(
                core_models.ConversationEvent.conversation_id == conv.id,
                core_models.ConversationEvent.type == "re_funnel",
            )
            .order_by(core_models.ConversationEvent.id.desc())
        )
        ev = self.db.execute(stmt).scalars().first()
        if ev and isinstance(ev.payload, dict):
            criteria = dict(ev.payload)

        stmt_c = (
            select(core_models.ConversationEvent)
            .where(
                core_models.ConversationEvent.conversation_id == conv.id,
                core_models.ConversationEvent.type == "re_campaign",
            )
            .order_by(core_models.ConversationEvent.id.desc())
        )
        camp_ev = self.db.execute(stmt_c).scalars().first()
        campaign_data: dict = {}
        if camp_ev and isinstance(camp_ev.payload, dict):
            campaign_data = dict(camp_ev.payload)
            if campaign_data.get("purpose") and not criteria.get("purpose"):
                criteria["purpose"] = campaign_data["purpose"]

        def save_criteria(next_state: str) -> None:
            conv.last_state = next_state
            self.db.add(conv)
            self._record_event(conv.id, "re_funnel", criteria)

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

        if last == "location_city":
            if len(text) < 2:
                return "Informe a cidade (ex: Campinas)."
            criteria["city"] = user_text.strip()
            save_criteria("location_state")
            return "Anotado. Qual o estado (UF)? (ex: SP)"

        if last == "location_state":
            uf = text.upper().replace(" ", "")
            if len(uf) != 2:
                return "Informe a UF com 2 letras (ex: SP)."
            criteria["state"] = uf
            save_criteria("type")
            return "Certo. Prefere apartamento ou casa?"

        if last == "type":
            if text in {"ap", "apto", "apartamento", "apartment"}:
                criteria["type"] = "apartment"
            elif text in {"casa", "house"}:
                criteria["type"] = "house"
            else:
                return "Digite 'apartamento' ou 'casa'."
            save_criteria("bedrooms")
            return "Quantos dormitórios? (ex: 2)"

        if last == "bedrooms":
            try:
                n = int("".join(ch for ch in text if ch.isdigit()))
                criteria["bedrooms"] = n
                save_criteria("price")
                return "Qual a faixa de preço? (ex: 2000-3500 ou 'ate 3000')"
            except Exception:
                return "Informe um número de dormitórios (ex: 2)."

        if last == "price":
            min_p, max_p = self._parse_price(user_text)
            if min_p is not None:
                criteria["min_price"] = min_p
            if max_p is not None:
                criteria["max_price"] = max_p

            lead = self._get_latest_lead_for_contact(tenant.id, contact.id)
            if not lead:
                # This should not happen if webhook creates the lead first, but as a fallback:
                lead = re_models.Lead.create_for_contact(tenant.id, contact.id, wa_id)

            lead.provide_preferences(criteria)
            # Apply campaign data after preferences
            lead.campaign_source = campaign_data.get("campaign_source")
            lead.campaign_medium = campaign_data.get("campaign_medium")
            lead.campaign_name = campaign_data.get("campaign_name")
            lead.campaign_content = campaign_data.get("campaign_content")
            lead.landing_url = campaign_data.get("landing_url")
            lead.external_property_id = campaign_data.get("external_property_id")
            lead.property_interest_id = campaign_data.get("property_id")
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)

            inquiry = re_models.Inquiry(
                tenant_id=tenant.id,
                lead_id=lead.id,
                property_id=campaign_data.get("property_id"),
                type=re_models.InquiryType.buy if criteria.get("purpose") == "sale" else re_models.InquiryType.rent,
                status=re_models.InquiryStatus.new,
                payload=criteria,
            )
            self.db.add(inquiry)
            self.db.commit()

            stmt = select(re_models.Property).where(re_models.Property.is_active == True)
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
            rows = self.db.execute(stmt).scalars().all()

            conv.last_state = "done"
            self.db.add(conv)

            if not rows:
                lead.status = re_models.LeadStatus.sem_imovel_disponivel
                self.db.add(lead)
                self.db.commit()
                return "Obrigado! Registrei sua preferência. No momento não encontrei imóveis com esse perfil. Quer ajustar a faixa de preço ou dormitórios?"

            search_results_summary = [{"id": p.id, "title": p.title} for p in rows]
            lead.mark_as_qualified(search_results_summary)
            self.db.add(lead)
            self.db.commit()

            lines = ["Encontrei estas opções:"]
            for p in rows:
                lines.append(f"#{p.id} - {p.title} | R$ {p.price:,.0f} | {p.address_city}-{p.address_state}")
            lines.append("Deseja ver mais detalhes? Envie o número do imóvel (ex: 3).")
            return "\n".join(lines)

        conv.last_state = "purpose"
        self.db.add(conv)
        self.db.commit()
        return "Vamos começar! Você procura compra ou locação?"

    def _normalize_text(self, s: str) -> str:
        return s.strip().lower()

    def _ensure_tenant(self, tenant_id: int) -> core_models.Tenant:
        tenant = self.db.get(core_models.Tenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        return tenant

    def _ensure_contact(self, tenant_id: int, wa_id: str) -> core_models.Contact:
        stmt = select(core_models.Contact).where(
            core_models.Contact.tenant_id == tenant_id,
            core_models.Contact.wa_id == wa_id,
        )
        c = self.db.execute(stmt).scalar_one_or_none()
        if not c:
            c = core_models.Contact(tenant_id=tenant_id, wa_id=wa_id)
            self.db.add(c)
            self.db.commit()
            self.db.refresh(c)
        return c

    def _ensure_conversation(self, tenant_id: int, contact_id: int) -> core_models.Conversation:
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
        conv = self.db.execute(stmt).scalars().first()
        if not conv:
            conv = core_models.Conversation(
                tenant_id=tenant_id,
                contact_id=contact_id,
                status=core_models.ConversationStatus.active_bot,
            )
            self.db.add(conv)
            self.db.commit()
            self.db.refresh(conv)
        return conv

    def _record_event(self, conversation_id: int, type_: str, payload: dict) -> None:
        self.db.add(core_models.ConversationEvent(conversation_id=conversation_id, type=type_, payload=payload))
        self.db.commit()

    def _get_latest_lead_for_contact(self, tenant_id: int, contact_id: int) -> re_models.Lead | None:
        stmt = (
            select(re_models.Lead)
            .where(re_models.Lead.tenant_id == tenant_id, re_models.Lead.contact_id == contact_id)
            .order_by(re_models.Lead.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def _parse_price(self, text: str) -> tuple[float | None, float | None]:
        t = self._normalize_text(text).replace("r$", "").replace(" ", "")
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

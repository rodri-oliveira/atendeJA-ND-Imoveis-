"""
Serviço de gerenciamento de leads.
Responsabilidade: Lógica de negócio relacionada a leads.
"""
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.domain.realestate.models import Lead


class LeadService:
    """Serviço para operações com leads."""
    
    @staticmethod
    def create_lead(db: Session, lead_data: Dict[str, Any]) -> Lead:
        """
        Cria um novo lead no banco de dados.
        
        Args:
            db: Sessão do banco de dados
            lead_data: Dicionário com dados do lead
            
        Returns:
            Lead criado
        """
        now = datetime.utcnow()
        lead = Lead(
            tenant_id=1,
            name=lead_data.get("nome"),
            phone=lead_data.get("telefone"),
            email=lead_data.get("email"),
            source=lead_data.get("origem", "whatsapp"),
            preferences=lead_data.get("preferencias"),
            consent_lgpd=bool(lead_data.get("consentimento_lgpd", False)),
            property_interest_id=lead_data.get("property_interest_id"),
            contact_id=lead_data.get("contact_id"),
            external_property_id=lead_data.get("external_property_id"),
            finalidade=lead_data.get("finalidade"),
            tipo=lead_data.get("tipo"),
            cidade=lead_data.get("cidade"),
            estado=lead_data.get("estado"),
            bairro=lead_data.get("bairro"),
            dormitorios=lead_data.get("dormitorios"),
            preco_min=lead_data.get("preco_min"),
            preco_max=lead_data.get("preco_max"),
            campaign_source=lead_data.get("campaign_source"),
            campaign_medium=lead_data.get("campaign_medium"),
            campaign_name=lead_data.get("campaign_name"),
            campaign_content=lead_data.get("campaign_content"),
            landing_url=lead_data.get("landing_url"),
            status=lead_data.get("status", "qualificado"),
            last_inbound_at=now,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    
    @staticmethod
    def create_unqualified_lead(
        db: Session,
        sender_id: str,
        state: Dict[str, Any],
        lgpd_consent: bool = False
    ) -> Lead:
        """
        Cria lead sem resultados (para campanhas futuras).
        
        Args:
            db: Sessão do banco de dados
            sender_id: ID do remetente (telefone)
            state: Estado da conversa com preferências
            lgpd_consent: Consentimento LGPD
            
        Returns:
            Lead criado
        """
        lead_data = {
            "nome": None,
            "telefone": sender_id,
            "email": None,
            "origem": "whatsapp",
            "consentimento_lgpd": lgpd_consent,
            "preferencias": state,
            "finalidade": state.get("purpose"),
            "tipo": state.get("type"),
            "cidade": state.get("city"),
            "bairro": state.get("neighborhood"),
            "dormitorios": state.get("bedrooms"),
            "preco_min": state.get("price_min"),
            "preco_max": state.get("price_max"),
            "status": "sem_imovel_disponivel",
        }
        return LeadService.create_lead(db, lead_data)

    # ===== Helpers de status (upsert por telefone) =====
    @staticmethod
    def _extract_phone(sender_id: str) -> str:
        return sender_id.split("@")[0] if "@" in (sender_id or "") else sender_id

    @staticmethod
    def upsert_lead_status(
        db: Session,
        phone: str,
        state: Dict[str, Any],
        status: str,
        name: str | None = None,
        email: str | None = None,
        property_id: int | None = None,
    ) -> Lead:
        lead = db.query(Lead).filter(Lead.phone == phone).order_by(Lead.id.desc()).first()
        if lead:
            lead.status = status
            lead.last_inbound_at = datetime.utcnow()
            try:
                lead.preferences = state
            except Exception:
                pass
            if property_id:
                lead.property_interest_id = property_id
            if name:
                lead.name = name
            if email:
                lead.email = email
            db.commit()
            db.refresh(lead)
            return lead
        else:
            lead_data = {
                "nome": name,
                "telefone": phone,
                "email": email,
                "origem": "whatsapp",
                "consentimento_lgpd": state.get("lgpd_consent", False),
                "preferencias": state,
                "finalidade": state.get("purpose"),
                "tipo": state.get("type"),
                "cidade": state.get("city"),
                "bairro": state.get("neighborhood"),
                "dormitorios": state.get("bedrooms"),
                "preco_min": state.get("price_min"),
                "preco_max": state.get("price_max"),
                "property_interest_id": property_id,
                "status": status,
            }
            return LeadService.create_lead(db, lead_data)

    @staticmethod
    def mark_qualified(db: Session, sender_id: str, state: Dict[str, Any]) -> Lead:
        phone = LeadService._extract_phone(sender_id)
        name = state.get("user_name")
        prop_id = state.get("interested_property_id") or state.get("directed_property_id")
        return LeadService.upsert_lead_status(db, phone, state, "qualificado", name=name, property_id=prop_id)
    
    @staticmethod
    def create_qualified_lead(
        db: Session,
        sender_id: str,
        name: str,
        email: str,
        state: Dict[str, Any],
        property_id: int
    ) -> Lead:
        """
        Cria lead qualificado (com interesse em imóvel específico).
        
        Args:
            db: Sessão do banco de dados
            sender_id: ID do remetente (telefone)
            name: Nome completo
            email: E-mail
            state: Estado da conversa
            property_id: ID do imóvel de interesse
            
        Returns:
            Lead criado
        """
        lead_data = {
            "nome": name,
            "telefone": sender_id,
            "email": email,
            "origem": "whatsapp",
            "consentimento_lgpd": state.get("lgpd_consent", False),
            "preferencias": state,
            "finalidade": state.get("purpose"),
            "tipo": state.get("type"),
            "cidade": state.get("city"),
            "bairro": state.get("neighborhood"),
            "dormitorios": state.get("bedrooms"),
            "preco_min": state.get("price_min"),
            "preco_max": state.get("price_max"),
            "property_interest_id": property_id,
            "status": "agendamento_pendente",
        }
        return LeadService.create_lead(db, lead_data)

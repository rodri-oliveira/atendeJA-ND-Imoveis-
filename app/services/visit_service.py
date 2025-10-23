"""
Serviço para gerenciar agendamentos de visitas.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.domain.realestate.models import VisitSchedule, Lead, Property, VisitStatus
import structlog
import re

log = structlog.get_logger()


class VisitService:
    """Serviço para criar e gerenciar agendamentos de visitas."""
    
    @staticmethod
    def create_visit_schedule(
        db: Session,
        sender_id: str,
        property_id: int,
        phone: str,
        preferred_date: Optional[str] = None,
        preferred_time: Optional[str] = None,
        notes: Optional[str] = None
    ) -> VisitSchedule:
        """
        Cria um agendamento de visita.
        
        Args:
            db: Sessão do banco
            sender_id: ID do remetente (WhatsApp)
            property_id: ID do imóvel
            phone: Telefone de contato
            preferred_date: Data preferida (formato livre)
            preferred_time: Horário preferido (formato livre)
            notes: Observações adicionais
            
        Returns:
            VisitSchedule criado
        """
        # Buscar ou criar Lead
        lead = db.query(Lead).filter(Lead.sender_id == sender_id).first()
        if not lead:
            lead = Lead(
                sender_id=sender_id,
                status="agendado",
                created_at=datetime.utcnow()
            )
            db.add(lead)
            db.flush()
        else:
            lead.status = "agendado"
            lead.updated_at = datetime.utcnow()
        
        # Criar agendamento
        visit = VisitSchedule(
            lead_id=lead.id,
            property_id=property_id,
            phone=phone,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            notes=notes,
            status="requested",
            created_at=datetime.utcnow()
        )
        
        db.add(visit)
        db.commit()
        db.refresh(visit)
        
        log.info(
            "visit_schedule_created",
            visit_id=visit.id,
            lead_id=lead.id,
            property_id=property_id,
            phone=phone,
            preferred_date=preferred_date,
            preferred_time=preferred_time
        )
        
        return visit
    
    @staticmethod
    def get_pending_visits(db: Session, sender_id: str) -> list[VisitSchedule]:
        """Retorna visitas pendentes de um lead."""
        lead = db.query(Lead).filter(Lead.sender_id == sender_id).first()
        if not lead:
            return []
        
        return (
            db.query(VisitSchedule)
            .filter(
                VisitSchedule.lead_id == lead.id,
                VisitSchedule.status.in_(["requested", "confirmed"])
            )
            .all()
        )
    
    @staticmethod
    def confirm_visit(db: Session, visit_id: int) -> VisitSchedule:
        """Confirma um agendamento de visita."""
        visit = db.query(VisitSchedule).filter(VisitSchedule.id == visit_id).first()
        if not visit:
            raise ValueError(f"Visit {visit_id} not found")
        
        visit.status = "confirmed"
        visit.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(visit)
        
        log.info("visit_confirmed", visit_id=visit_id)
        return visit
    
    @staticmethod
    def cancel_visit(db: Session, visit_id: int, reason: Optional[str] = None) -> VisitSchedule:
        """Cancela um agendamento de visita."""
        visit = db.query(VisitSchedule).filter(VisitSchedule.id == visit_id).first()
        if not visit:
            raise ValueError(f"Visit {visit_id} not found")
        
        visit.status = "cancelled"
        if reason:
            visit.notes = f"{visit.notes or ''}\nMotivo cancelamento: {reason}".strip()
        visit.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(visit)
        
        log.info("visit_cancelled", visit_id=visit_id, reason=reason)
        return visit
    
    @staticmethod
    def validate_phone(text: str) -> Tuple[bool, Optional[str]]:
        """
        Valida e formata número de telefone brasileiro.
        
        Returns:
            (is_valid, formatted_phone)
        """
        # Remove tudo que não é dígito
        digits = re.sub(r'\D', '', text)
        
        # Aceitar formatos: 11964442592, 5511964442592, +5511964442592
        if len(digits) == 11:  # DDD + número
            return (True, digits)
        elif len(digits) == 13 and digits.startswith('55'):  # +55 DDD número
            return (True, digits[2:])  # Remove código do país
        elif len(digits) == 10:  # DDD + número sem 9
            return (True, digits)
        else:
            return (False, None)
    
    @staticmethod
    def parse_date_input(text: str) -> Optional[datetime]:
        """
        Interpreta entrada de data em linguagem natural.
        
        Aceita:
        - "hoje", "amanhã", "depois de amanhã"
        - "segunda", "terça", etc.
        - "DD/MM", "DD/MM/YYYY"
        """
        text_lower = text.lower().strip()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Atalhos
        if "hoje" in text_lower:
            return today
        if "amanh" in text_lower:  # amanhã, amanha
            return today + timedelta(days=1)
        if "depois" in text_lower and "amanh" in text_lower:
            return today + timedelta(days=2)
        
        # Dias da semana
        weekdays = {
            "segunda": 0, "seg": 0,
            "terça": 1, "terca": 1, "ter": 1,
            "quarta": 2, "qua": 2,
            "quinta": 3, "qui": 3,
            "sexta": 4, "sex": 4,
            "sábado": 5, "sabado": 5, "sab": 5,
            "domingo": 6, "dom": 6
        }
        for day_name, day_num in weekdays.items():
            if day_name in text_lower:
                days_ahead = (day_num - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Próxima semana
                return today + timedelta(days=days_ahead)
        
        # Formato DD/MM ou DD/MM/YYYY
        match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year
            if year < 100:
                year += 2000
            try:
                return datetime(year, month, day)
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def parse_time_input(text: str, visit_date: datetime) -> Optional[datetime]:
        """
        Interpreta entrada de horário.
        
        Aceita:
        - "14h", "14:00", "14h30", "14:30"
        - "manhã" (9h), "tarde" (14h), "noite" (19h)
        """
        text_lower = text.lower().strip()
        
        # Períodos genéricos
        if "manh" in text_lower:
            return visit_date.replace(hour=9, minute=0)
        if "tarde" in text_lower:
            return visit_date.replace(hour=14, minute=0)
        if "noite" in text_lower:
            return visit_date.replace(hour=19, minute=0)
        
        # Formato HH:MM ou HHhMM ou HH
        match = re.search(r'(\d{1,2})(?:[h:](\d{2}))?', text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return visit_date.replace(hour=hour, minute=minute)
        
        return None
    
    @staticmethod
    def create_visit(
        db: Session,
        lead_id: int,
        property_id: int,
        phone: str,
        visit_datetime: datetime,
        notes: Optional[str] = None
    ) -> int:
        """
        Cria agendamento de visita (compatibilidade com handler antigo).
        
        Returns:
            ID do agendamento criado
        """
        # Buscar tenant_id do lead
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        tenant_id = lead.tenant_id if lead else 1
        
        now = datetime.utcnow()
        visit = VisitSchedule(
            tenant_id=tenant_id,
            lead_id=lead_id,
            property_id=property_id,
            scheduled_datetime=visit_datetime,
            scheduled_date=visit_datetime.strftime("%Y-%m-%d"),
            scheduled_time=visit_datetime.strftime("%H:%M"),
            contact_phone=phone,
            contact_name=lead.name if lead else None,
            notes=notes,
            status="requested",
            created_at=now,
            updated_at=now
        )
        
        db.add(visit)
        db.commit()
        db.refresh(visit)
        
        # Atualizar status do lead
        if lead:
            lead.status = "agendado"
            db.commit()
        
        log.info(
            "visit_created",
            visit_id=visit.id,
            lead_id=lead_id,
            property_id=property_id,
            visit_datetime=visit_datetime.isoformat()
        )
        
        return visit.id

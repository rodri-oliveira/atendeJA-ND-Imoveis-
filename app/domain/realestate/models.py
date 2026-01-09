from __future__ import annotations
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Boolean,
    JSON,
    Index,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.repositories.db import Base


class PropertyType(str, Enum):
    apartment = "apartment"
    house = "house"
    land = "land"
    commercial = "commercial"


class PropertyPurpose(str, Enum):
    sale = "sale"
    rent = "rent"


class LeadStatus(str, Enum):
    iniciado = "iniciado"
    novo = "novo"
    qualificado = "qualificado"
    sem_imovel_disponivel = "sem_imovel_disponivel"
    agendamento_pendente = "agendamento_pendente"
    agendado = "agendado"
    sem_resposta_24h = "sem_resposta_24h"


class ChatbotFlow(Base):
    __tablename__ = "re_chatbot_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    domain: Mapped[str] = mapped_column(String(64), default="real_estate", index=True)
    name: Mapped[str] = mapped_column(String(160))

    flow_definition: Mapped[dict] = mapped_column(JSON)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_version: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(180), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("uix_re_chatbot_flow_tenant_name", "tenant_id", "name", unique=True),
        Index("idx_re_chatbot_flow_tenant_domain_published", "tenant_id", "domain", "is_published"),
    )


class Property(Base):
    __tablename__ = "re_properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    type: Mapped[PropertyType] = mapped_column(SAEnum(PropertyType))
    purpose: Mapped[PropertyPurpose] = mapped_column(SAEnum(PropertyPurpose), index=True)

    price: Mapped[float] = mapped_column(Float, index=True)
    condo_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    iptu: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Integrações / Importação
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at_source: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Código interno de referência (ex.: A1273)
    ref_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    # Localização (colunas normalizadas para filtros + JSON opcional)
    address_city: Mapped[str] = mapped_column(String(120), index=True)
    address_state: Mapped[str] = mapped_column(String(2), index=True)
    address_neighborhood: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    address_json: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Características
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suites: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parking_spots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_usable: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[list[PropertyImage]] = relationship(back_populates="property", cascade="all, delete-orphan")  # type: ignore
    amenities: Mapped[list[PropertyAmenity]] = relationship(back_populates="property", cascade="all, delete-orphan")  # type: ignore

    __table_args__ = (
        Index("idx_re_prop_tenant_purpose_type_city", "tenant_id", "purpose", "type", "address_city"),
        Index("idx_re_prop_price", "price"),
        Index("idx_re_prop_active", "is_active"),
        Index("uix_re_prop_tenant_external", "tenant_id", "external_id", unique=True),
    )


class PropertyImage(Base):
    __tablename__ = "re_property_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("re_properties.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    property: Mapped[Property] = relationship(back_populates="images")


class Amenity(Base):
    __tablename__ = "re_amenities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)

    __table_args__ = (
        Index("uix_re_amenity_tenant_slug", "tenant_id", "slug", unique=True),
    )


class PropertyAmenity(Base):
    __tablename__ = "re_property_amenities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("re_properties.id"), index=True)
    amenity_id: Mapped[int] = mapped_column(ForeignKey("re_amenities.id"), index=True)

    property: Mapped[Property] = relationship(back_populates="amenities")
    amenity: Mapped[Amenity] = relationship()

    __table_args__ = (
        Index("uix_re_prop_amenity", "property_id", "amenity_id", unique=True),
    )


class PropertyExternalRef(Base):
    __tablename__ = "re_property_external_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)  # chavesnamao, facebook, instagram, etc.
    external_id: Mapped[str] = mapped_column(String(160))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("re_properties.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InvalidLeadStatusTransition(Exception):
    pass

class Lead(Base):
    __tablename__ = "re_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    preferences: Mapped[dict | None] = mapped_column(JSON, default=None)
    consent_lgpd: Mapped[bool] = mapped_column(Boolean, default=False)
    campaign_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    campaign_medium: Mapped[str | None] = mapped_column(String(32), nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    campaign_content: Mapped[str | None] = mapped_column(String(120), nullable=True)
    landing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_property_id: Mapped[str | None] = mapped_column(String(160), nullable=True)

    status: Mapped[LeadStatus] = mapped_column(SAEnum(LeadStatus), default=LeadStatus.novo, index=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    property_interest_id: Mapped[int | None] = mapped_column(ForeignKey("re_properties.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    finalidade: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    tipo: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    dormitorios: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    preco_min: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    preco_max: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @staticmethod
    def create_for_contact(tenant_id: int, contact_id: int, phone: str) -> Lead:
        return Lead(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone=phone,
            source="whatsapp",
            status=LeadStatus.iniciado,
            last_inbound_at=datetime.utcnow(),
        )

    def provide_preferences(self, criteria: dict):
        if self.status not in [LeadStatus.iniciado, LeadStatus.novo]:
            raise InvalidLeadStatusTransition(f"Cannot provide preferences for lead in state {self.status}")
        
        self.preferences = criteria
        self.finalidade = criteria.get("purpose")
        self.tipo = criteria.get("type")
        self.cidade = criteria.get("city")
        self.estado = criteria.get("state")
        self.dormitorios = criteria.get("bedrooms")
        self.preco_min = criteria.get("min_price")
        self.preco_max = criteria.get("max_price")
        
        self._transition_to(LeadStatus.novo)

    def mark_as_qualified(self, search_results: list):
        if self.status != LeadStatus.novo:
            raise InvalidLeadStatusTransition(f"Cannot mark as qualified lead in state {self.status}")
        
        if not self.preferences:
            self.preferences = {}
        self.preferences['search_results'] = search_results
        self._transition_to(LeadStatus.qualificado)

    def request_visit(self):
        if self.status not in [LeadStatus.qualificado, LeadStatus.agendamento_pendente]:
            raise InvalidLeadStatusTransition(f"Cannot request visit for lead in state {self.status}")
        self._transition_to(LeadStatus.agendamento_pendente)

    def _transition_to(self, new_status: LeadStatus):
        self.status = new_status
        self.status_updated_at = datetime.utcnow()

    def change_status(self, new_status: LeadStatus):
        # Para ações manuais do usuário (Kanban), permitimos transições mais flexíveis,
        # mas ainda podemos adicionar regras aqui se necessário (ex: não reverter de 'agendado' para 'novo')
        if not isinstance(new_status, LeadStatus):
            raise ValueError("Invalid status provided")
        self._transition_to(new_status)

    def reactivate_if_needed(self):
        if self.status == LeadStatus.sem_resposta_24h:
            # A lógica de qualificação é complexa e depende de buscas, então por ora
            # a regra mais simples é voltar para 'novo' para re-engajar no funil.
            # Uma versão mais avançada poderia chamar um 'LeadQualificationService'.
            self._transition_to(LeadStatus.novo)



class InquiryType(str, Enum):
    buy = "buy"
    rent = "rent"
    question = "question"


class InquiryStatus(str, Enum):
    new = "new"
    in_progress = "in_progress"
    closed = "closed"


class Inquiry(Base):
    __tablename__ = "re_inquiries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    lead_id: Mapped[int | None] = mapped_column(ForeignKey("re_leads.id"), nullable=True, index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("re_properties.id"), nullable=True, index=True)

    type: Mapped[InquiryType] = mapped_column(SAEnum(InquiryType), index=True)
    status: Mapped[InquiryStatus] = mapped_column(SAEnum(InquiryStatus), default=InquiryStatus.new, index=True)

    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisitStatus(str, Enum):
    requested = "requested"
    confirmed = "confirmed"
    canceled = "canceled"
    done = "done"


class VisitSchedule(Base):
    __tablename__ = "re_visit_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    property_id: Mapped[int] = mapped_column(ForeignKey("re_properties.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("re_leads.id"), index=True)

    scheduled_datetime: Mapped[datetime] = mapped_column(DateTime)
    scheduled_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scheduled_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

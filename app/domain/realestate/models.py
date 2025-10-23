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


class Lead(Base):
    __tablename__ = "re_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # whatsapp, site, instagram, etc.

    preferences: Mapped[dict | None] = mapped_column(JSON, default=None)  # filtros desejados
    consent_lgpd: Mapped[bool] = mapped_column(Boolean, default=False)
    # Campanhas / atribuição
    campaign_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    campaign_medium: Mapped[str | None] = mapped_column(String(32), nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    campaign_content: Mapped[str | None] = mapped_column(String(120), nullable=True)
    landing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_property_id: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # Status e timestamps de interação
    status: Mapped[str] = mapped_column(String(32), default="novo", index=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Direcionamento e integrações
    property_interest_id: Mapped[int | None] = mapped_column(ForeignKey("re_properties.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # FK removida temporariamente

    # Preferências denormalizadas para filtros
    finalidade: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    tipo: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    dormitorios: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    preco_min: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    preco_max: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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

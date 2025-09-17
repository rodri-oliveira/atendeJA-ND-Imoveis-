from __future__ import annotations
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Integer, DateTime, Enum as SAEnum, ForeignKey, Boolean, JSON, Index, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class ConversationStatus(str, Enum):
    active_bot = "active_bot"
    human_handoff = "human_handoff"
    closed = "closed"


class UserRole(str, Enum):
    admin = "admin"
    collaborator = "collaborator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.collaborator, index=True)

    __table_args__ = (
        Index("uix_user_email", "email", unique=True),
    )


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)

    contacts: Mapped[list[Contact]] = relationship(back_populates="tenant")  # type: ignore


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    wa_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    do_not_disturb: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="contacts")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="contact")  # type: ignore

    __table_args__ = (
        Index("uix_contact_tenant_wa", "tenant_id", "wa_id", unique=True),
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    status: Mapped[ConversationStatus] = mapped_column(SAEnum(ConversationStatus), default=ConversationStatus.active_bot)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contact: Mapped[Contact] = relationship(back_populates="conversations")


class MessageDirection(str, Enum):
    inbound = "inbound"
    outbound = "outbound"


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(SAEnum(MessageDirection))
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="received")
    wa_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("uix_wa_message_id", "tenant_id", "wa_message_id", unique=True),
        Index("uix_idempotency_key", "tenant_id", "idempotency_key", unique=True),
    )


class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# Removidos modelos de pizzaria/lanches para focar no domínio imobiliário


class SuppressedContact(Base):
    """Lista de supressão/opt-out por tenant (não enviar mensagens)."""

    __tablename__ = "suppressed_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    wa_id: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("uix_suppressed_tenant_wa", "tenant_id", "wa_id", unique=True),
    )


class MessageLog(Base):
    """Log de envios via provider para rastreabilidade/auditoria."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    to: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # text|template|read
    body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    provider_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_msglog_tenant_to", "tenant_id", "to"),
        Index("idx_msglog_created", "created_at"),
    )

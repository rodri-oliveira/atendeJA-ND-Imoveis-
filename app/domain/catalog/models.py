from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repositories.db import Base


class CatalogItemType(Base):
    __tablename__ = "catalog_item_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    key: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))

    schema: Mapped[dict] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("uix_catalog_item_type_tenant_key", "tenant_id", "key", unique=True),
    )


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    item_type_id: Mapped[int] = mapped_column(ForeignKey("catalog_item_types.id"), index=True)

    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    attributes: Mapped[dict] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    item_type: Mapped[CatalogItemType] = relationship()  # type: ignore
    media: Mapped[list[CatalogMedia]] = relationship(back_populates="item", cascade="all, delete-orphan")  # type: ignore
    external_refs: Mapped[list[CatalogExternalReference]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )  # type: ignore

    __table_args__ = (
        Index("idx_catalog_item_tenant_type_active", "tenant_id", "item_type_id", "is_active"),
    )


class CatalogMedia(Base):
    __tablename__ = "catalog_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), index=True)

    kind: Mapped[str] = mapped_column(String(32), default="image")
    url: Mapped[str] = mapped_column(String(1000))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped[CatalogItem] = relationship(back_populates="media")  # type: ignore

    __table_args__ = (
        Index("idx_catalog_media_item_sort", "item_id", "sort_order"),
    )


class CatalogExternalReference(Base):
    __tablename__ = "catalog_external_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    item_type_id: Mapped[int] = mapped_column(Integer, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), index=True)

    source: Mapped[str] = mapped_column(String(120), index=True)
    external_key: Mapped[str] = mapped_column(String(128), index=True)
    url: Mapped[str] = mapped_column(String(1000))

    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    item: Mapped[CatalogItem] = relationship(back_populates="external_refs")  # type: ignore

    __table_args__ = (
        Index(
            "uix_catalog_extref_tenant_source_key",
            "tenant_id",
            "source",
            "external_key",
            unique=True,
        ),
        Index("idx_catalog_extref_tenant_type", "tenant_id", "item_type_id"),
    )


class CatalogIngestionRun(Base):
    __tablename__ = "catalog_ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)

    source_base_url: Mapped[str] = mapped_column(String(1000))

    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_catalog_ingestion_tenant_started", "tenant_id", "started_at"),
    )


class CatalogIngestionError(Base):
    __tablename__ = "catalog_ingestion_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("catalog_ingestion_runs.id"), index=True)

    url: Mapped[str] = mapped_column(String(1000))
    error: Mapped[str] = mapped_column(String(400))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_catalog_ingestion_error_run", "run_id"),
    )

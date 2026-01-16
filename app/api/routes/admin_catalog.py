from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require_admin_tenant_id
from app.core.config import settings
from app.domain.catalog.models import CatalogItem, CatalogItemType, CatalogMedia, CatalogExternalReference
from app.domain.catalog.schema import validate_attributes, validate_item_type_schema
from app.domain.vehicles_ingestion.service import VehicleIngestionService
from app.api.schemas.catalog import CatalogItemOut, CatalogMediaOut


def _looks_like_image_url(url: str) -> bool:
    u = str(url or "").strip().lower()
    if not u:
        return False
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if u.endswith(ext) or f"{ext}?" in u or f"{ext}#" in u:
            return True
    return False


class CatalogItemCreateIn(BaseModel):
    item_type_key: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=220)
    description: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CatalogItemUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    attributes: dict[str, Any] | None = None
    is_active: bool | None = None


class CatalogMediaCreateIn(BaseModel):
    kind: str = Field(default="image", min_length=1, max_length=32)
    url: str = Field(..., min_length=1, max_length=2048)


class CatalogMediaReorderIn(BaseModel):
    media_ids: list[int] = Field(default_factory=list)


router = APIRouter()


def _ensure_vehicle_schema(*, db: Session, item_type: CatalogItemType) -> None:
    if not item_type or (item_type.key or "").strip() != "vehicle":
        return

    vehicle_schema = {
        "fields": [
            {"key": "price", "label": "Preço", "type": "number", "required": False},
            {"key": "year", "label": "Ano", "type": "number", "required": False},
            {"key": "km", "label": "KM", "type": "number", "required": False},
            {"key": "make", "label": "Marca", "type": "string", "required": False},
            {"key": "model", "label": "Modelo", "type": "string", "required": False},
            {"key": "transmission", "label": "Câmbio", "type": "string", "required": False},
            {"key": "fuel", "label": "Combustível", "type": "string", "required": False},
            {"key": "accessories", "label": "Acessórios", "type": "string_list", "required": False},
        ]
    }

    try:
        validate_item_type_schema(schema=dict(getattr(item_type, "schema", {}) or {}))
        existing_fields = (item_type.schema or {}).get("fields") if isinstance(item_type.schema, dict) else None
        if not existing_fields:
            raise ValueError("empty_schema")
        return
    except Exception:
        item_type.schema = vehicle_schema
        db.add(item_type)
        db.commit()
        db.refresh(item_type)


@router.get("/catalog/items", response_model=list[CatalogItemOut])
def list_catalog_items(
    item_type_key: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    query = db.query(CatalogItem).options(joinedload(CatalogItem.media)).filter(CatalogItem.tenant_id == tenant_id)

    if item_type_key:
        item_type = (
            db.query(CatalogItemType)
            .filter(
                CatalogItemType.tenant_id == tenant_id,
                CatalogItemType.key == item_type_key,
            )
            .first()
        )
        if not item_type:
            return []
        query = query.filter(CatalogItem.item_type_id == item_type.id)

    rows = query.order_by(CatalogItem.id.desc()).limit(limit).offset(offset).all()
    return rows


@router.post("/catalog/items", response_model=CatalogItemOut)
def create_catalog_item(
    payload: CatalogItemCreateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    key = (payload.item_type_key or "").strip()
    item_type = (
        db.query(CatalogItemType)
        .filter(
            CatalogItemType.tenant_id == int(tenant_id),
            CatalogItemType.key == key,
            CatalogItemType.is_active == True,  # noqa: E712
        )
        .first()
    )
    if item_type is None:
        raise HTTPException(status_code=404, detail="item_type_not_found")

    _ensure_vehicle_schema(db=db, item_type=item_type)

    try:
        validate_attributes(schema=dict(getattr(item_type, "schema", {}) or {}), attributes=payload.attributes or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = CatalogItem(
        tenant_id=int(tenant_id),
        item_type_id=int(item_type.id),
        title=str(payload.title),
        description=(payload.description or None),
        attributes=dict(payload.attributes or {}),
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/catalog/items/{item_id}", response_model=CatalogItemOut)
def get_catalog_item(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    row = (
        db.query(CatalogItem)
        .options(joinedload(CatalogItem.media))
        .filter(CatalogItem.id == int(item_id))
        .first()
    )
    if not row or int(row.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")
    return row


@router.get("/catalog/items/{item_id}/media", response_model=list[CatalogMediaOut])
def list_catalog_item_media(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    item = db.get(CatalogItem, int(item_id))
    if not item or int(item.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")

    rows = (
        db.query(CatalogMedia)
        .filter(CatalogMedia.tenant_id == int(tenant_id), CatalogMedia.item_id == int(item_id))
        .order_by(CatalogMedia.sort_order.asc(), CatalogMedia.id.asc())
        .all()
    )
    return [
        CatalogMediaOut(
            id=int(m.id),
            item_id=int(m.item_id),
            kind=str(m.kind),
            url=str(m.url),
            sort_order=int(m.sort_order),
        )
        for m in rows
    ]


@router.delete("/catalog/items/{item_id}/hard")
def hard_delete_catalog_item(
    item_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    row = db.get(CatalogItem, int(item_id))
    if not row or int(row.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")

    db.query(CatalogMedia).filter(CatalogMedia.tenant_id == int(tenant_id), CatalogMedia.item_id == int(item_id)).delete()
    db.query(CatalogExternalReference).filter(
        CatalogExternalReference.tenant_id == int(tenant_id),
        CatalogExternalReference.item_id == int(item_id),
    ).delete()

    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/catalog/items/{item_id}/media", response_model=CatalogMediaOut)
def add_catalog_item_media(
    item_id: int,
    payload: CatalogMediaCreateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    item = db.get(CatalogItem, int(item_id))
    if not item or int(item.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")

    kind = (payload.kind or "image").strip() or "image"
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url_required")
    if kind == "image" and not _looks_like_image_url(url):
        raise HTTPException(status_code=400, detail="invalid_image_url")

    max_sort = (
        db.query(CatalogMedia.sort_order)
        .filter(CatalogMedia.tenant_id == int(tenant_id), CatalogMedia.item_id == int(item_id))
        .order_by(CatalogMedia.sort_order.desc())
        .limit(1)
        .scalar()
    )
    next_sort = int(max_sort) + 1 if max_sort is not None else 0

    m = CatalogMedia(
        tenant_id=int(tenant_id),
        item_id=int(item_id),
        kind=kind,
        url=url,
        sort_order=next_sort,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return CatalogMediaOut(
        id=int(m.id),
        item_id=int(m.item_id),
        kind=str(m.kind),
        url=str(m.url),
        sort_order=int(m.sort_order),
    )


@router.delete("/catalog/media/{media_id}")
def delete_catalog_media(
    media_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    m = db.get(CatalogMedia, int(media_id))
    if not m or int(m.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="media_not_found")

    db.delete(m)
    db.commit()
    return {"deleted": True}


@router.post("/catalog/items/{item_id}/media/reorder")
def reorder_catalog_item_media(
    item_id: int,
    payload: CatalogMediaReorderIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    item = db.get(CatalogItem, int(item_id))
    if not item or int(item.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")

    ids = [int(x) for x in (payload.media_ids or [])]
    if not ids:
        raise HTTPException(status_code=400, detail="media_ids_required")

    rows = (
        db.query(CatalogMedia)
        .filter(CatalogMedia.tenant_id == int(tenant_id), CatalogMedia.item_id == int(item_id), CatalogMedia.id.in_(ids))
        .all()
    )
    found = {int(r.id) for r in rows}
    missing = [mid for mid in ids if int(mid) not in found]
    if missing:
        raise HTTPException(status_code=400, detail="media_not_found")

    by_id = {int(r.id): r for r in rows}
    for idx, mid in enumerate(ids):
        by_id[int(mid)].sort_order = int(idx)
        db.add(by_id[int(mid)])
    db.commit()
    return {"reordered": True}


@router.patch("/catalog/items/{item_id}", response_model=CatalogItemOut)
def update_catalog_item(
    item_id: int,
    payload: CatalogItemUpdateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    row = db.get(CatalogItem, int(item_id))
    if not row or int(row.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_not_found")

    item_type = db.get(CatalogItemType, int(row.item_type_id))
    if not item_type or int(item_type.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_type_not_found")

    _ensure_vehicle_schema(db=db, item_type=item_type)

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        row.title = str(data["title"]).strip() or row.title
    if "description" in data:
        row.description = (str(data["description"]).strip() if data["description"] is not None else None)
    if "attributes" in data and data["attributes"] is not None:
        try:
            validate_attributes(schema=dict(getattr(item_type, "schema", {}) or {}), attributes=data["attributes"] or {})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        row.attributes = dict(data["attributes"] or {})
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

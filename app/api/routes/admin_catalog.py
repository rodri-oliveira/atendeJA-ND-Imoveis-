from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_tenant_id, require_admin_request_context
from app.core.config import settings
from app.domain.catalog.schema import validate_attributes, validate_item_type_schema
from app.domain.vehicles_ingestion.service import VehicleIngestionService
from app.domain.catalog.models import CatalogItem, CatalogItemType, CatalogMedia
from app.api.schemas.catalog import CatalogItemOut


if settings.APP_ENV == "test":
    router = APIRouter()
else:
    router = APIRouter(dependencies=[Depends(require_admin_request_context)])


class CatalogDiscoverIn(BaseModel):
    base_url: str = Field(..., min_length=3)
    max_listing_pages: int = Field(4, ge=0, le=20)
    max_detail_links: int = Field(400, ge=0, le=1000)


class CatalogRunIn(BaseModel):
    base_url: str = Field(..., min_length=3)
    max_listings: int = Field(30, ge=1, le=200)
    timeout_seconds: float = Field(10.0, ge=2.0, le=60.0)
    max_listing_pages: int = Field(4, ge=0, le=20)


@router.post("/catalog/ingestion/discover")
async def catalog_ingestion_discover(
    payload: CatalogDiscoverIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    try:
        svc = VehicleIngestionService(db=db, tenant_id=int(tenant_id))
        return await svc.discover(
            base_url=payload.base_url,
            max_listing_pages=int(payload.max_listing_pages),
            max_detail_links=int(payload.max_detail_links),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "discover_failed", "message": str(e)})


@router.post("/catalog/ingestion/run")
async def catalog_ingestion_run(
    payload: CatalogRunIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    try:
        svc = VehicleIngestionService(db=db, tenant_id=int(tenant_id))
        res = await svc.run(
            base_url=payload.base_url,
            max_listings=int(payload.max_listings),
            timeout_seconds=float(payload.timeout_seconds),
            max_listing_pages=int(payload.max_listing_pages),
        )
        return {
            "run_id": res.run_id,
            "discovered": res.discovered,
            "processed": res.processed,
            "created": res.created,
            "updated": res.updated,
            "errors": res.errors,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "run_failed", "message": str(e)})


@router.get("/catalog/items", response_model=List[CatalogItemOut])
def list_catalog_items(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
    item_type_key: str = Query("vehicle", description="Filter by item type key"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    item_type = (
        db.query(CatalogItemType)
        .filter(
            CatalogItemType.tenant_id == tenant_id,
            CatalogItemType.key == item_type_key
        )
        .first()
    )

    if not item_type:
        return []

    items = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.tenant_id == tenant_id,
            CatalogItem.item_type_id == item_type.id
        )
        .order_by(CatalogItem.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return items


class CatalogItemTypeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    tenant_id: int
    key: str
    name: str
    item_schema: dict = Field(default_factory=dict, validation_alias="schema", serialization_alias="schema")
    is_active: bool


class CatalogItemTypeCreateIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=160)
    item_schema: dict = Field(default_factory=dict, validation_alias="schema", serialization_alias="schema")
    is_active: bool = True


class CatalogItemTypeUpdateIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    item_schema: dict | None = Field(default=None, validation_alias="schema", serialization_alias="schema")
    is_active: bool | None = None


@router.get("/catalog/item-types", response_model=List[CatalogItemTypeOut])
def list_catalog_item_types(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
    include_inactive: bool = False,
):
    q = db.query(CatalogItemType).filter(CatalogItemType.tenant_id == int(tenant_id))
    if not include_inactive:
        q = q.filter(CatalogItemType.is_active == True)  # noqa: E712
    rows = q.order_by(CatalogItemType.key.asc(), CatalogItemType.id.asc()).all()
    return [
        CatalogItemTypeOut(
            id=int(r.id),
            tenant_id=int(r.tenant_id),
            key=str(r.key),
            name=str(r.name),
            item_schema=dict(getattr(r, "schema", {}) or {}),
            is_active=bool(r.is_active),
        )
        for r in rows
    ]


@router.post("/catalog/item-types", response_model=CatalogItemTypeOut)
def create_catalog_item_type(
    payload: CatalogItemTypeCreateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    key = (payload.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key_required")

    exists = (
        db.query(CatalogItemType)
        .filter(CatalogItemType.tenant_id == int(tenant_id), CatalogItemType.key == key)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="item_type_already_exists")

    # validate schema format (will raise ValueError on invalid)
    try:
        validate_item_type_schema(schema=payload.item_schema or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = CatalogItemType(
        tenant_id=int(tenant_id),
        key=key,
        name=(payload.name or "").strip() or key,
        schema=dict(payload.item_schema or {}),
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CatalogItemTypeOut(
        id=int(row.id),
        tenant_id=int(row.tenant_id),
        key=str(row.key),
        name=str(row.name),
        item_schema=dict(getattr(row, "schema", {}) or {}),
        is_active=bool(row.is_active),
    )


@router.patch("/catalog/item-types/{item_type_id}", response_model=CatalogItemTypeOut)
def update_catalog_item_type(
    item_type_id: int,
    payload: CatalogItemTypeUpdateIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_admin_tenant_id),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    row = db.get(CatalogItemType, int(item_type_id))
    if not row or int(row.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="item_type_not_found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        row.name = (str(data["name"]).strip() or row.name)
    if "item_schema" in data and data["item_schema"] is not None:
        try:
            validate_item_type_schema(schema=data["item_schema"] or {})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        row.schema = dict(data["item_schema"] or {})
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return CatalogItemTypeOut(
        id=int(row.id),
        tenant_id=int(row.tenant_id),
        key=str(row.key),
        name=str(row.name),
        item_schema=dict(getattr(row, "schema", {}) or {}),
        is_active=bool(row.is_active),
    )


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


class CatalogMediaOut(BaseModel):
    id: int
    item_id: int
    kind: str
    url: str
    sort_order: int


class CatalogMediaCreateIn(BaseModel):
    kind: str = Field(default="image", min_length=1, max_length=32)
    url: str = Field(..., min_length=3, max_length=1000)


class CatalogMediaReorderIn(BaseModel):
    media_ids: list[int] = Field(default_factory=list)


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
    if not item_type:
        raise HTTPException(status_code=404, detail="item_type_not_found")

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
        kind=(payload.kind or "image").strip() or "image",
        url=(payload.url or "").strip(),
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

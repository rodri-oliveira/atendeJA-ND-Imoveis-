from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_user_tenant_id
from app.api.schemas.catalog import CatalogItemOut
from app.domain.catalog.models import CatalogItem, CatalogItemType

router = APIRouter()


@router.get("/catalog/items", response_model=List[CatalogItemOut])
def list_catalog_items(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_user_tenant_id),
    item_type_key: str = Query("vehicle", description="Filter by item type key"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    item_type = (
        db.query(CatalogItemType)
        .filter(CatalogItemType.tenant_id == int(tenant_id), CatalogItemType.key == item_type_key)
        .first()
    )
    if not item_type:
        return []

    items = (
        db.query(CatalogItem)
        .filter(CatalogItem.tenant_id == int(tenant_id), CatalogItem.item_type_id == int(item_type.id))
        .order_by(CatalogItem.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return items

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.domain.catalog.models import (
    CatalogExternalReference,
    CatalogIngestionError,
    CatalogIngestionRun,
    CatalogItem,
    CatalogItemType,
    CatalogMedia,
)
from app.domain.vehicles_ingestion.discovery import discover_site
from app.domain.vehicles_ingestion.extractor import VehicleListing, external_key_from_url, normalize_url, parse_vehicle_listing


@dataclass(frozen=True)
class RunResult:
    run_id: int
    discovered: int
    processed: int
    created: int
    updated: int
    errors: int


class VehicleIngestionService:
    def __init__(self, *, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = int(tenant_id)

    def _get_or_create_vehicle_type(self) -> CatalogItemType:
        t = (
            self.db.query(CatalogItemType)
            .filter(CatalogItemType.tenant_id == self.tenant_id, CatalogItemType.key == "vehicle")
            .first()
        )
        if t:
            return t
        t = CatalogItemType(tenant_id=self.tenant_id, key="vehicle", name="Veículos", schema={})
        self.db.add(t)
        self.db.flush()
        return t

    def _upsert_listing(self, *, item_type: CatalogItemType, source: str, listing: VehicleListing) -> tuple[bool, CatalogItem]:
        ext_key = external_key_from_url(listing.url)
        existing_ref = (
            self.db.query(CatalogExternalReference)
            .filter(
                CatalogExternalReference.tenant_id == self.tenant_id,
                CatalogExternalReference.source == source,
                CatalogExternalReference.external_key == ext_key,
            )
            .first()
        )

        now = datetime.utcnow()

        if existing_ref is not None:
            item = self.db.get(CatalogItem, int(existing_ref.item_id))
            if item is None:
                item = CatalogItem(
                    tenant_id=self.tenant_id,
                    item_type_id=int(item_type.id),
                    title=listing.title or "Sem título",
                    description=listing.description,
                    attributes=self._to_attributes(listing),
                    is_active=True,
                )
                self.db.add(item)
                self.db.flush()
                existing_ref.item_id = int(item.id)
                existing_ref.item_type_id = int(item_type.id)

            item.title = listing.title or item.title
            item.description = listing.description
            item.attributes = self._to_attributes(listing)
            item.is_active = True

            existing_ref.url = normalize_url(listing.url)
            existing_ref.last_seen_at = now

            self._sync_media(item=item, listing=listing)
            return (False, item)

        item = CatalogItem(
            tenant_id=self.tenant_id,
            item_type_id=int(item_type.id),
            title=listing.title or "Sem título",
            description=listing.description,
            attributes=self._to_attributes(listing),
            is_active=True,
        )
        self.db.add(item)
        self.db.flush()

        ref = CatalogExternalReference(
            tenant_id=self.tenant_id,
            item_type_id=int(item_type.id),
            item_id=int(item.id),
            source=source,
            external_key=ext_key,
            url=normalize_url(listing.url),
            last_seen_at=now,
        )
        self.db.add(ref)

        self._sync_media(item=item, listing=listing)
        return (True, item)

    def _sync_media(self, *, item: CatalogItem, listing: VehicleListing) -> None:
        # Minimal sync: if we have images, replace current set with up to 10
        if not listing.images:
            return
        self.db.query(CatalogMedia).filter(CatalogMedia.item_id == int(item.id)).delete()
        for i, url in enumerate(listing.images[:10]):
            m = CatalogMedia(
                tenant_id=self.tenant_id,
                item_id=int(item.id),
                kind="image",
                url=url,
                sort_order=i,
            )
            self.db.add(m)

    def _to_attributes(self, listing: VehicleListing) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if listing.price is not None:
            attrs["price"] = listing.price
        if listing.year is not None:
            attrs["year"] = listing.year
        if listing.km is not None:
            attrs["km"] = listing.km
        if listing.make:
            attrs["make"] = listing.make
        if listing.model:
            attrs["model"] = listing.model
        if listing.transmission:
            attrs["transmission"] = listing.transmission
        if listing.fuel:
            attrs["fuel"] = listing.fuel
        return attrs

    async def discover(
        self, *, base_url: str, max_listing_pages: int, max_detail_links: int
    ) -> dict[str, Any]:
        res = await discover_site(
            base_url=base_url,
            max_listing_pages=max_listing_pages,
            max_detail_links=max_detail_links,
        )
        return {
            "base_url": res.base_url,
            "domain": res.domain,
            "sitemaps": res.sitemaps,
            "listing_candidates": res.listing_candidates,
            "detail_candidates_sample": res.detail_candidates[:20],
            "detail_candidates_total": len(res.detail_candidates),
        }

    async def run(
        self,
        *,
        base_url: str,
        max_listings: int = 30,
        timeout_seconds: float = 10.0,
        max_listing_pages: int = 4,
        run_id: int | None = None,
    ) -> RunResult:
        item_type = self._get_or_create_vehicle_type()

        if run_id is not None:
            run = self.db.get(CatalogIngestionRun, int(run_id))
            if run is None:
                raise ValueError("run_not_found")
            run.source_base_url = str(base_url)
            run.status = "running"
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
        else:
            run = CatalogIngestionRun(tenant_id=self.tenant_id, source_base_url=base_url, status="running")
            self.db.add(run)
            self.db.flush()

        discovered = processed = created = updated = errors = 0

        res = await discover_site(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_listing_pages=max_listing_pages,
            max_detail_links=max_listings,  # Limit discovery to what we will process
        )
        source = res.domain

        # Prefer detail candidates; if none, fallback to listing candidates.
        detail_urls = res.detail_candidates[:max_listings]
        discovered = len(detail_urls)
        run.discovered_count = int(discovered)
        self.db.add(run)
        self.db.commit()

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            for u in detail_urls:
                try:
                    r = await client.get(u)
                    if r.status_code >= 400:
                        raise RuntimeError(f"http_{r.status_code}")
                    listing = parse_vehicle_listing(html=r.text or "", page_url=u)

                    is_created, _ = self._upsert_listing(item_type=item_type, source=source, listing=listing)
                    processed += 1
                    if is_created:
                        created += 1
                    else:
                        updated += 1

                    run.processed_count = int(processed)
                    run.created_count = int(created)
                    run.updated_count = int(updated)
                    self.db.commit()

                except Exception as e:
                    errors += 1
                    err = CatalogIngestionError(
                        tenant_id=self.tenant_id,
                        run_id=int(run.id),
                        url=str(u),
                        error=str(e)[:400],
                    )
                    self.db.add(err)
                    self.db.commit()

        run.status = "finished"
        run.finished_at = datetime.utcnow()
        run.processed_count = int(processed)
        run.created_count = int(created)
        run.updated_count = int(updated)
        self.db.add(run)
        self.db.commit()

        return RunResult(
            run_id=int(run.id),
            discovered=int(discovered),
            processed=int(processed),
            created=int(created),
            updated=int(updated),
            errors=int(errors),
        )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import structlog
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


log = structlog.get_logger()


class VehicleIngestionService:
    def __init__(self, *, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = int(tenant_id)
        self.log = log.bind(tenant_id=self.tenant_id)

    def _build_description(self, listing: VehicleListing) -> str | None:
        base = (listing.description or "").strip() or None
        accessories = [str(x).strip() for x in (getattr(listing, "accessories", None) or []) if str(x).strip()]

        if not accessories:
            return base

        # Enrich if missing/weak
        if base is None or len(base) < 40:
            return "Acessórios: " + ", ".join(accessories[:30])

        # Append if not already present
        if "acess" not in base.lower():
            return base + "\n\nAcessórios: " + ", ".join(accessories[:30])

        return base

    def _get_or_create_vehicle_type(self) -> CatalogItemType:
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

        t = (
            self.db.query(CatalogItemType)
            .filter(CatalogItemType.tenant_id == self.tenant_id, CatalogItemType.key == "vehicle")
            .first()
        )
        if t:
            # If created in older versions with empty/invalid schema, upgrade in place.
            try:
                from app.domain.catalog.schema import validate_item_type_schema

                validate_item_type_schema(schema=dict(t.schema or {}))
                existing_fields = (t.schema or {}).get("fields") if isinstance(t.schema, dict) else None
                if not existing_fields:
                    raise ValueError("empty_schema")
            except Exception:
                t.schema = vehicle_schema
                self.db.add(t)
                self.db.commit()
                self.db.refresh(t)
            return t
        t = CatalogItemType(tenant_id=self.tenant_id, key="vehicle", name="Veículos", schema=vehicle_schema)
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
                    description=self._build_description(listing),
                    attributes=self._to_attributes(listing),
                    is_active=True,
                )
                self.db.add(item)
                self.db.flush()
                existing_ref.item_id = int(item.id)
                existing_ref.item_type_id = int(item_type.id)

            item.title = listing.title or item.title
            item.description = self._build_description(listing)
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
            description=self._build_description(listing),
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
        accessories = [str(x).strip() for x in (getattr(listing, "accessories", None) or []) if str(x).strip()]
        if accessories:
            attrs["accessories"] = accessories[:40]
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
        self.log.info("ingestion.run.start", run_id=run_id, base_url=base_url)
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

        self.log.info("ingestion.discover.start", run_id=run.id)
        res = await discover_site(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_listing_pages=max_listing_pages,
            max_detail_links=max_listings,  # Limit discovery to what we will process
        )
        self.log.info("ingestion.discover.end", run_id=run.id, discovered_count=len(res.detail_candidates))
        source = res.domain

        # Prefer detail candidates; if none, fallback to listing candidates.
        base_norm = normalize_url(base_url)
        listing_norm = normalize_url(base_norm.rstrip("/") + "/veiculos")
        filtered_detail_urls: list[str] = []
        for u in res.detail_candidates:
            un = normalize_url(str(u))
            if un == base_norm:
                continue
            # Never ingest listing pages as vehicle items
            if un == listing_norm or un.endswith("/veiculos"):
                continue
            filtered_detail_urls.append(str(u))

        detail_urls = filtered_detail_urls[:max_listings]
        discovered = len(detail_urls)
        run.discovered_count = int(discovered)
        self.db.add(run)
        self.db.commit()

        self.log.info("ingestion.processing.start", run_id=run.id, url_count=len(detail_urls))

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            for i, u in enumerate(detail_urls):
                try:
                    self.log.info("ingestion.processing.url", run_id=run.id, url=u, index=i)
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
                    self.log.error("ingestion.processing.error", run_id=run.id, url=u, error=str(e))
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

        self.log.info("ingestion.run.end", run_id=run.id, status="finished")

        return RunResult(
            run_id=int(run.id),
            discovered=int(discovered),
            processed=int(processed),
            created=int(created),
            updated=int(updated),
            errors=int(errors),
        )

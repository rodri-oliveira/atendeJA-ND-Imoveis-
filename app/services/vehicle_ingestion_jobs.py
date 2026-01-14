from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.repositories.db import db_session
import anyio

from app.domain.catalog.models import CatalogIngestionError, CatalogIngestionRun
from app.domain.vehicles_ingestion.service import VehicleIngestionService


@dataclass(frozen=True)
class EnqueueVehicleIngestionResult:
    run_id: int
    status: str


def run_vehicle_ingestion_job(*, tenant_id: int, run_id: int, base_url: str, max_listings: int, timeout_seconds: float, max_listing_pages: int) -> None:
    """Background job: executes vehicle ingestion and updates CatalogIngestionRun.

    IMPORTANT: runs in a fresh DB session (do not reuse request session).
    """
    with db_session() as db:
        run = db.get(CatalogIngestionRun, int(run_id))
        if not run:
            return
        run.status = "running"
        db.add(run)
        db.commit()

        try:
            anyio.run(
                VehicleIngestionService(db=db, tenant_id=int(tenant_id)).run,
                run_id=int(run_id),
                base_url=base_url,
                max_listings=int(max_listings),
                timeout_seconds=float(timeout_seconds),
                max_listing_pages=int(max_listing_pages),
            )
        except Exception as e:
            # Persist a summary error row and mark run as error
            db.add(
                CatalogIngestionError(
                    tenant_id=int(tenant_id),
                    run_id=int(run_id),
                    url=str(base_url),
                    error=str(e)[:400],
                )
            )
            run.status = "error"
            run.finished_at = datetime.utcnow()
            db.add(run)
            db.commit()


def enqueue_vehicle_ingestion(
    *,
    tenant_id: int,
    base_url: str,
    max_listings: int,
    timeout_seconds: float,
    max_listing_pages: int,
) -> EnqueueVehicleIngestionResult:
    """Create a queued CatalogIngestionRun and return its run_id.

    Scheduling the background job is responsibility of the caller.
    """
    with db_session() as db:
        run = CatalogIngestionRun(
            tenant_id=int(tenant_id),
            source_base_url=str(base_url),
            status="queued",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return EnqueueVehicleIngestionResult(run_id=int(run.id), status=str(run.status))

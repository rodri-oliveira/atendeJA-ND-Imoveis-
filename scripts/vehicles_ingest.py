from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.vehicle_ingestion_jobs import enqueue_vehicle_ingestion, run_vehicle_ingestion_job


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="One-off vehicle ingestion (scraping) for a given tenant.")
    p.add_argument("--tenant-id", type=int, required=True)
    p.add_argument("--base-url", type=str, required=True)
    p.add_argument("--max-listings", type=int, default=30)
    p.add_argument("--timeout-seconds", type=float, default=10.0)
    p.add_argument("--max-listing-pages", type=int, default=4)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Mantém compatibilidade com outros scripts (não obrigar variáveis específicas aqui)
    os.environ.setdefault("APP_ENV", os.getenv("APP_ENV", "dev"))

    enqueue = enqueue_vehicle_ingestion(
        tenant_id=int(args.tenant_id),
        base_url=str(args.base_url),
        max_listings=int(args.max_listings),
        timeout_seconds=float(args.timeout_seconds),
        max_listing_pages=int(args.max_listing_pages),
    )

    print(f"Enqueued ingestion run_id={enqueue.run_id} status={enqueue.status}")

    run_vehicle_ingestion_job(
        tenant_id=int(args.tenant_id),
        run_id=int(enqueue.run_id),
        base_url=str(args.base_url),
        max_listings=int(args.max_listings),
        timeout_seconds=float(args.timeout_seconds),
        max_listing_pages=int(args.max_listing_pages),
    )

    print(f"Finished ingestion run_id={enqueue.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.db import SessionLocal
from app.domain.catalog.models import CatalogExternalReference, CatalogItem
from app.domain.vehicles_ingestion.service import VehicleIngestionService


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Reprocess existing vehicle URLs already stored in CatalogExternalReference (updates items in DB)."
        )
    )
    p.add_argument("--tenant-id", type=int, required=True)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--timeout-seconds", type=float, default=15.0)
    p.add_argument(
        "--only-missing",
        action="store_true",
        help="Only reprocess items missing key attributes (price/km/make/model).",
    )
    p.add_argument("--commit-every", type=int, default=10)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tenant_id = int(args.tenant_id)
    limit = int(args.limit)
    only_missing = bool(args.only_missing)
    commit_every = max(1, int(args.commit_every))

    from app.domain.vehicles_ingestion.extractor import parse_vehicle_listing

    with SessionLocal() as db:
        refs = (
            db.query(CatalogExternalReference)
            .filter(CatalogExternalReference.tenant_id == tenant_id)
            .order_by(CatalogExternalReference.id.desc())
            .limit(limit)
            .all()
        )

        print(f"Found refs to reprocess: {len(refs)}")

        svc = VehicleIngestionService(db=db, tenant_id=tenant_id)
        item_type = svc._get_or_create_vehicle_type()  # internal reuse (avoid duplication)

        processed = updated = errors = 0

        def is_missing(it: CatalogItem) -> bool:
            a = (it.attributes or {}) if isinstance(it.attributes, dict) else {}
            if a.get("price") is None:
                return True
            if a.get("km") is None:
                return True
            mk = (a.get("make") or "").strip().lower() if isinstance(a.get("make"), str) else ""
            md = (a.get("model") or "").strip() if isinstance(a.get("model"), str) else ""
            if not mk or mk in {"veiculo", "veículo", "carro"}:
                return True
            if not md or md in {"-", "–", "—"}:
                return True
            return False

        with httpx.Client(timeout=float(args.timeout_seconds), follow_redirects=True) as client:
            for ref in refs:
                url = str(ref.url or '').strip()
                if not url:
                    continue
                try:
                    it = db.get(CatalogItem, int(ref.item_id))
                    if it is None:
                        continue
                    if only_missing and not is_missing(it):
                        continue

                    processed += 1
                    r = client.get(url)
                    if r.status_code >= 400:
                        raise RuntimeError(f"http_{r.status_code}")

                    listing = parse_vehicle_listing(html=r.text or '', page_url=url)
                    svc._upsert_listing(item_type=item_type, source=str(ref.source or ''), listing=listing)
                    updated += 1

                    if updated % commit_every == 0:
                        db.commit()
                except Exception as e:
                    db.rollback()
                    errors += 1
                    print(f"ERROR url={url} err={e}")

        db.commit()

        print(f"processed={processed} updated={updated} errors={errors}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

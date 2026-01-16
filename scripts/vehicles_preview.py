from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.vehicles_ingestion.discovery import discover_site
from app.domain.vehicles_ingestion.extractor import parse_vehicle_listing


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Vehicle scraping preview (dry-run). Does NOT write to DB.")
    p.add_argument("--base-url", type=str, required=True)
    p.add_argument("--max-listing-pages", type=int, default=4)
    p.add_argument("--max-detail-links", type=int, default=60)
    p.add_argument("--sample", type=int, default=10)
    p.add_argument("--timeout-seconds", type=float, default=15.0)
    p.add_argument("--pretty", action="store_true")
    return p


def _quality_score(row: dict) -> dict:
    attrs = (row.get("attributes") or {}) if isinstance(row.get("attributes"), dict) else {}

    fields = {
        "price": attrs.get("price"),
        "km": attrs.get("km"),
        "year": attrs.get("year"),
        "make": attrs.get("make"),
        "model": attrs.get("model"),
        "description": row.get("description"),
    }

    present = {k: bool(v) for k, v in fields.items()}
    coverage = sum(1 for v in present.values() if v) / max(1, len(present))

    images = row.get("images") or []
    accessories = attrs.get("accessories") or []

    return {
        "present": present,
        "coverage": round(coverage, 3),
        "images_count": len(images) if isinstance(images, list) else 0,
        "accessories_count": len(accessories) if isinstance(accessories, list) else 0,
    }


async def _amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    res = await discover_site(
        base_url=str(args.base_url),
        timeout_seconds=float(args.timeout_seconds),
        max_listing_pages=int(args.max_listing_pages),
        max_detail_links=int(args.max_detail_links),
    )

    detail_urls = [str(u) for u in (res.detail_candidates or [])][: int(args.sample)]
    print(f"Discovered detail urls: {len(res.detail_candidates or [])} (showing {len(detail_urls)})")

    out_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=float(args.timeout_seconds), follow_redirects=True) as client:
        for i, url in enumerate(detail_urls):
            r = await client.get(url)
            if r.status_code >= 400:
                out_rows.append({"url": url, "error": f"http_{r.status_code}"})
                continue

            listing = parse_vehicle_listing(html=r.text or "", page_url=url)
            attrs = {
                "price": listing.price,
                "km": listing.km,
                "year": listing.year,
                "make": listing.make,
                "model": listing.model,
                "transmission": listing.transmission,
                "fuel": listing.fuel,
                "accessories": listing.accessories,
            }

            row = {
                "index": i,
                "url": url,
                "title": listing.title,
                "description": listing.description,
                "attributes": {k: v for k, v in attrs.items() if v not in (None, "", [], {})},
                "images": listing.images,
            }
            row["quality"] = _quality_score(row)
            out_rows.append(row)

    if args.pretty:
        print(json.dumps(out_rows, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(out_rows, ensure_ascii=False))

    coverages = [float((r.get("quality") or {}).get("coverage") or 0.0) for r in out_rows if isinstance(r, dict)]
    if coverages:
        avg = sum(coverages) / max(1, len(coverages))
        print(f"Avg coverage: {round(avg, 3)}")

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())

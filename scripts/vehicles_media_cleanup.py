from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.db import SessionLocal
from app.domain.catalog.models import CatalogMedia


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cleanup vehicle catalog media (remove repeated/logo/banner assets).")
    p.add_argument("--tenant-id", type=int, required=True)
    p.add_argument("--repeat-threshold", type=int, default=3)
    p.add_argument("--apply", action="store_true")
    return p


def _is_layout_like(url: str | None) -> bool:
    if not url:
        return True
    u = str(url).strip().lower()
    if u.startswith("data:"):
        return True
    if u.endswith(".svg") or u.endswith(".ico"):
        return True
    patterns = [
        r"logo",
        r"favicon",
        r"sprite",
        r"icon",
        r"brand",
        r"banner",
        r"header",
        r"footer",
        r"navbar",
        r"menu",
        r"social",
        r"whatsapp",
        r"facebook",
        r"instagram",
        r"tiktok",
        r"placeholder",
        r"noimage",
        r"default",
    ]
    return any(re.search(p, u) for p in patterns)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tenant_id = int(args.tenant_id)

    with SessionLocal() as db:
        rows = (
            db.query(CatalogMedia)
            .filter(CatalogMedia.tenant_id == tenant_id)
            .order_by(CatalogMedia.item_id.asc(), CatalogMedia.sort_order.asc(), CatalogMedia.id.asc())
            .all()
        )

        print(f"Total media rows: {len(rows)}")

        by_url = Counter([str(r.url).strip() for r in rows if r.url])
        repeated_urls = {u for u, c in by_url.items() if c >= int(args.repeat_threshold)}

        to_remove = []
        for r in rows:
            u = str(r.url).strip() if r.url else ""
            if not u:
                to_remove.append(r)
                continue
            if _is_layout_like(u):
                to_remove.append(r)
                continue
            if u in repeated_urls:
                to_remove.append(r)
                continue

        print(f"Repeated URLs (>= {int(args.repeat_threshold)}): {len(repeated_urls)}")
        print(f"To remove: {len(to_remove)}")

        if to_remove:
            print("Examples to remove:")
            for r in to_remove[:10]:
                print(f"  - media_id={r.id} item_id={r.item_id} url={r.url}")

        if not args.apply:
            resp = input("Apply removal and reorder? (s/n): ")
            if resp.strip().lower() != "s":
                print("Canceled.")
                return 0

        removed_ids = {int(r.id) for r in to_remove}
        for r in to_remove:
            db.delete(r)
        db.commit()

        # Reorder remaining media per item
        remaining = (
            db.query(CatalogMedia)
            .filter(CatalogMedia.tenant_id == tenant_id)
            .order_by(CatalogMedia.item_id.asc(), CatalogMedia.sort_order.asc(), CatalogMedia.id.asc())
            .all()
        )
        grouped: dict[int, list[CatalogMedia]] = defaultdict(list)
        for r in remaining:
            grouped[int(r.item_id)].append(r)

        updated = 0
        for item_id, medias in grouped.items():
            for idx, m in enumerate(medias):
                if int(m.sort_order) != int(idx):
                    m.sort_order = int(idx)
                    db.add(m)
                    updated += 1
        db.commit()

        print(f"Removed: {len(removed_ids)}")
        print(f"Reordered sort_order updates: {updated}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

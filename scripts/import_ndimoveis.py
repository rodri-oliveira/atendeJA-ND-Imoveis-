from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import httpx

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.db import SessionLocal
from app.domain.realestate.sources import ndimoveis as nd
from app.domain.realestate.importer import upsert_property


def _cache_path(tenant_id: int, finalidades: list[str]) -> Path:
    fin = "_".join(sorted(set(finalidades)))
    return Path(__file__).resolve().parent / f".nd_seen_urls_tenant{int(tenant_id)}_{fin}.json"


def _load_seen(cache_file: Path) -> set[str]:
    try:
        if not cache_file.exists():
            return set()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x) for x in data if x}
        return set()
    except Exception:
        return set()


def _save_seen(cache_file: Path, seen: set[str]) -> None:
    cache_file.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _iter_detail_urls(finalidade: str, page_start: int, max_pages: int) -> Iterable[str]:
    for page in range(page_start, page_start + max_pages):
        for list_url in nd.list_url_candidates(finalidade, page):
            yield list_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--finalidade", choices=["venda", "locacao", "both"], default="both")
    parser.add_argument("--page-start", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--limit-properties", type=int, default=100)
    parser.add_argument("--throttle-ms", type=int, default=250)
    parser.add_argument("--exhaust", action="store_true")
    parser.add_argument("--stop-after-empty-blocks", type=int, default=2)
    parser.add_argument("--cache-seen", action="store_true")
    parser.add_argument("--reset-cache", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    finalidades: list[str]
    if args.finalidade == "both":
        finalidades = ["venda", "locacao"]
    else:
        finalidades = [args.finalidade]

    discovered: list[str] = []
    cache_file = _cache_path(int(args.tenant_id), finalidades)
    seen: set[str] = set()
    if args.cache_seen and not args.reset_cache:
        seen = _load_seen(cache_file)

    list_stats: Counter[str] = Counter()
    list_status: Counter[int] = Counter()

    with httpx.Client(timeout=25.0, headers=nd.UA, verify=False, follow_redirects=True) as client:
        empty_blocks = 0
        block_start = int(args.page_start)
        while True:
            new_in_block = 0
            for fin in finalidades:
                for page in range(block_start, block_start + int(args.max_pages)):
                    found_links: list[str] = []
                    for list_url in nd.list_url_candidates(fin, page):
                        try:
                            r = client.get(list_url)
                            list_status[int(r.status_code)] += 1
                            if r.status_code != 200:
                                continue
                            links = nd.discover_list_links(r.text)
                            if links:
                                list_stats[f"{fin}_pages_with_links"] += 1
                                list_stats[f"{fin}_links_total"] += len(links)
                                found_links = links
                                break
                        except Exception:
                            list_stats[f"{fin}_errors"] += 1
                        finally:
                            time.sleep(max(0, int(args.throttle_ms)) / 1000.0)

                    for url in found_links:
                        if url in seen:
                            continue
                        seen.add(url)
                        discovered.append(url)
                        new_in_block += 1
                        if len(discovered) >= int(args.limit_properties):
                            break

                    if len(discovered) >= int(args.limit_properties):
                        break
                if len(discovered) >= int(args.limit_properties):
                    break

            if new_in_block == 0:
                empty_blocks += 1
            else:
                empty_blocks = 0

            if not args.exhaust:
                break
            if len(discovered) >= int(args.limit_properties):
                break
            if empty_blocks >= int(args.stop_after_empty_blocks):
                break
            block_start += int(args.max_pages)

    processed = 0
    created = 0
    updated = 0
    images_created = 0
    errors: list[dict] = []
    type_counts: Counter[str] = Counter()

    with httpx.Client(timeout=25.0, headers=nd.UA, verify=False, follow_redirects=True) as client:
        with SessionLocal() as db:
            for url in discovered:
                try:
                    r = client.get(url)
                    if r.status_code != 200:
                        errors.append({"url": url, "status": r.status_code})
                        continue
                    dto = nd.parse_detail(r.text, url)
                    if dto.ptype:
                        type_counts[str(dto.ptype)] += 1
                    processed += 1

                    if args.apply:
                        st, imgs = upsert_property(db, int(args.tenant_id), dto)
                        if st == "created":
                            created += 1
                        else:
                            updated += 1
                        images_created += int(imgs)
                except Exception as e:  # noqa: BLE001
                    errors.append({"url": url, "error": str(e)})
                finally:
                    time.sleep(max(0, int(args.throttle_ms)) / 1000.0)

            if args.apply:
                db.commit()

    if args.cache_seen:
        _save_seen(cache_file, seen)

    print("=" * 60)
    print("ND import – APPLY" if args.apply else "ND import – DRY RUN")
    print("=" * 60)
    print(f"tenant_id: {args.tenant_id}")
    print(f"finalidade: {args.finalidade}")
    print(f"pages: start={args.page_start} max={args.max_pages}")
    print(f"discovered_urls: {len(discovered)}")
    if args.cache_seen:
        print(f"cache_file: {cache_file}")
        print(f"seen_urls_total: {len(seen)}")
    if list_stats:
        print("list_discovery_stats:")
        for k, v in list_stats.most_common():
            print(f"  - {k}: {v}")
    if list_status:
        print("list_status_counts:")
        for code, c in sorted(list_status.items(), key=lambda x: (-x[1], x[0]))[:10]:
            print(f"  - {code}: {c}")
    print(f"processed: {processed}")
    if args.apply:
        print(f"created: {created}")
        print(f"updated: {updated}")
        print(f"images_created: {images_created}")
    print("ptype_counts (inferred from parse_detail):")
    for k, v in type_counts.most_common():
        print(f"  - {k}: {v}")
    if errors:
        print(f"errors: {len(errors)} (showing up to 20)")
        for e in errors[:20]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()

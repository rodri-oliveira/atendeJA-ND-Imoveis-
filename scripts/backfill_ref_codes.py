#!/usr/bin/env python3
"""
Backfill de códigos de referência (ref_code) em re_properties.

Boas práticas:
- Padrão de detecção conservador (sem adivinhar prefixos).
- Dry-run por padrão; usa --apply para escrever no banco.
- Suporta extração a partir de external_id e URLs em re_property_external_refs.
- Gera amostras e contagens para validação.

Uso:
  poetry run python scripts/backfill_ref_codes.py --dry-run
  poetry run python scripts/backfill_ref_codes.py --apply

Opcional:
  --tenant-id <id>  (filtra por tenant)
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Garantir que o diretório raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, update, and_, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import time

from app.repositories.db import SessionLocal
from app.domain.realestate.models import Property, PropertyExternalRef


CODE_RE = re.compile(r"^[A-Z]{1,3}\d{2,6}$")  # A1234, ND12345 etc.
DIGITS_RE = re.compile(r"^\d{2,6}$")           # 2 a 6 dígitos

# Extração a partir de URLs usuais: /imovel/<CODE>, ref=<CODE>
URL_PATTERNS = [
    re.compile(r"/imovel/([A-Z0-9]{2,10})", re.IGNORECASE),
    re.compile(r"ref[=:\-/]([A-Z0-9]{2,10})", re.IGNORECASE),
]


def extract_code_from_text(text: str | None) -> str | None:
    if not text:
        return None
    t = (text or "").strip().upper()
    # 1) Padrões de URL
    for pat in URL_PATTERNS:
        m = pat.search(t)
        if m:
            return m.group(1)
    # 2) Padrão alfanumérico tipo A1234
    if CODE_RE.match(t):
        return t
    # 3) Dígitos puros
    if DIGITS_RE.match(t):
        return t
    return None


def collect_candidates(db: Session, tenant_id: int | None = None) -> Tuple[List[Tuple[int, str]], Dict[str, int]]:
    """Coleta propriedades sem ref_code, propondo novo valor a partir de external_id ou refs externas.

    Retorna:
      - updates: lista de tuplas (property_id, novo_ref_code)
      - stats: contagens de origem
    """
    stats = {"from_external_id": 0, "from_external_ref_url": 0}
    updates: List[Tuple[int, str]] = []

    # 1) Buscar propriedades com ref_code vazio/nulo
    stmt = select(Property).where((Property.ref_code.is_(None)) | (Property.ref_code == ""))
    if tenant_id is not None:
        stmt = stmt.where(Property.tenant_id == tenant_id)
    props = db.execute(stmt).scalars().all()

    # 2) Mapear external refs por property_id
    ref_map: Dict[int, List[str]] = {}
    ref_stmt = select(PropertyExternalRef.property_id, PropertyExternalRef.url, PropertyExternalRef.external_id)
    if tenant_id is not None:
        ref_stmt = ref_stmt.where(PropertyExternalRef.tenant_id == tenant_id)
    for pid, url, ext_id in db.execute(ref_stmt).all():
        ref_map.setdefault(pid, []).append(url or ext_id or "")

    for p in props:
        # Tentar via external_id do próprio registro
        code = extract_code_from_text(p.external_id)
        if code:
            updates.append((p.id, code))
            stats["from_external_id"] += 1
            continue
        # Tentar via referências externas (URL / ref)
        for candidate in ref_map.get(p.id, []):
            code = extract_code_from_text(candidate)
            if code:
                updates.append((p.id, code))
                stats["from_external_ref_url"] += 1
                break

    # Remover duplicatas mantendo último pro mesmo id (caso raro)
    seen = {}
    dedup_updates: List[Tuple[int, str]] = []
    for pid, code in updates:
        seen[pid] = code
    for pid, code in seen.items():
        dedup_updates.append((pid, code))

    return dedup_updates, stats


def apply_updates(db: Session, updates: List[Tuple[int, str]], chunk_size: int = 50, retries: int = 5, backoff: float = 0.3) -> int:
    total = 0
    since_last_commit = 0
    for pid, code in updates:
        attempt = 0
        while True:
            try:
                db.execute(
                    update(Property)
                    .where(Property.id == pid)
                    .values(ref_code=code)
                )
                total += 1
                since_last_commit += 1
                if since_last_commit >= chunk_size:
                    db.commit()
                    since_last_commit = 0
                break
            except OperationalError:
                attempt += 1
                if attempt >= retries:
                    raise
                time.sleep(backoff * attempt)
    db.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de ref_code em re_properties")
    parser.add_argument("--apply", action="store_true", help="Aplica as alterações no banco")
    parser.add_argument("--tenant-id", type=int, default=None, help="Filtrar por tenant_id")
    parser.add_argument("--limit", type=int, default=50, help="Amostra a exibir no stdout")
    args = parser.parse_args()

    with SessionLocal() as db:  # type: ignore
        try:
            db.execute(text("PRAGMA busy_timeout=5000"))
        except Exception:
            pass
        updates, stats = collect_candidates(db, tenant_id=args.tenant_id)
        print("=" * 60)
        print("Backfill ref_code – DRY RUN" if not args.apply else "Backfill ref_code – APPLY")
        print("=" * 60)
        print(f"Candidates total: {len(updates)}")
        print(f"  - from external_id: {stats['from_external_id']}")
        print(f"  - from external_ref url: {stats['from_external_ref_url']}")

        # Amostra
        print("\nAmostra (property_id -> code):")
        for pid, code in updates[: args.limit]:
            print(f"  {pid} -> {code}")

        if args.apply and updates:
            written = apply_updates(db, updates)
            print(f"\n✅ Atualizados: {written}")
        elif not args.apply:
            print("\nModo dry-run: nenhuma alteração foi aplicada. Use --apply para escrever no banco.")


if __name__ == "__main__":
    main()

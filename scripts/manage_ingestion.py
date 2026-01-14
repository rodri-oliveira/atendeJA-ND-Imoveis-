import argparse
import asyncio
import json
import os
import sys

import httpx

# Add project root to path to allow imports from 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.repositories.db import db_session
from app.repositories.models import Tenant


# --- Tenant Management ---
def ensure_test_tenant():
    """Ensures tenant 101 exists for testing purposes."""
    with db_session() as db:
        tenant_id = 101
        tenant_name = "Loja de Veículos Teste"

        existing_by_id = db.get(Tenant, tenant_id)
        if existing_by_id:
            print(f"Tenant {tenant_id} already exists.")
            return

        existing_by_name = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if existing_by_name:
            print(f"Tenant with name '{tenant_name}' already exists with id {existing_by_name.id}.")
            return

        new_tenant = Tenant(id=tenant_id, name=tenant_name, is_active=True)
        db.add(new_tenant)
        db.commit()
        print(f"Tenant {tenant_id} ('{tenant_name}') created successfully.")


# --- Ingestion API Client ---
SUPER_ADMIN_KEY = os.getenv("SUPER_ADMIN_API_KEY", "dev")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

async def run_discovery(args):
    headers = {
        "X-Super-Admin-Key": SUPER_ADMIN_KEY,
        "X-Tenant-Id": str(args.tenant_id),
        "Content-Type": "application/json",
    }
    payload = {
        "base_url": args.base_url,
        "max_listing_pages": args.max_listing_pages,
        "max_detail_links": args.max_detail_links,
    }
    url = f"{API_BASE_URL.rstrip('/')}/admin/catalog/ingestion/discover"

    print(f"Running discovery for {payload['base_url']} on tenant {args.tenant_id}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=args.timeout)
            response.raise_for_status()
            data = response.json()
            print("\n--- Discovery Result ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\n--- Summary ---")
            print(f"Sitemaps found: {len(data.get('sitemaps', []))}")
            print(f"Listing candidates found: {len(data.get('listing_candidates', []))}")
            print(f"Detail candidates found: {data.get('detail_candidates_total', 0)}")
            print("\nDiscovery successful.")
    except Exception as e:
        _handle_api_error(e)


async def run_ingestion(args):
    headers = {
        "X-Super-Admin-Key": SUPER_ADMIN_KEY,
        "X-Tenant-Id": str(args.tenant_id),
        "Content-Type": "application/json",
    }
    payload = {
        "base_url": args.base_url,
        "max_listings": args.max_listings,
        "timeout_seconds": args.timeout,
        "max_listing_pages": args.max_listing_pages,
    }
    url = f"{API_BASE_URL.rstrip('/')}/admin/catalog/ingestion/run"

    print(f"Running ingestion for {payload['base_url']} on tenant {args.tenant_id}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=args.timeout + 15.0)
            response.raise_for_status()
            data = response.json()
            print("\n--- Ingestion Result ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\nIngestion successful.")
    except Exception as e:
        _handle_api_error(e)


def _handle_api_error(e):
    if isinstance(e, httpx.HTTPStatusError):
        print(f"\n--- ERROR: HTTP {e.response.status_code} ---")
        try:
            print(json.dumps(e.response.json(), indent=2))
        except json.JSONDecodeError:
            print(e.response.text)
    elif isinstance(e, httpx.RequestError):
        print(f"\n--- ERROR: Request failed ---")
        print(f"Could not connect to {e.request.url}.")
        print("Is the FastAPI server running?")
    else:
        print(f"\n--- UNEXPECTED ERROR ---")
        print(str(e))


# --- Main CLI --- 
def main():
    parser = argparse.ArgumentParser(description="Manage ingestion pipeline for the Catalog.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: ensure-test-tenant
    parser_tenant = subparsers.add_parser("ensure-test-tenant", help="Create tenant 101 for testing.")
    parser_tenant.set_defaults(func=lambda args: ensure_test_tenant())

    # Subcommand: discover
    parser_discover = subparsers.add_parser("discover", help="Run discovery on a site.")
    parser_discover.add_argument("base_url", help="The base URL of the site to discover.")
    parser_discover.add_argument("--tenant-id", type=int, default=101, help="Tenant ID to use.")
    parser_discover.add_argument("--max-listing-pages", type=int, default=5, help="Max listing pages to crawl.")
    parser_discover.add_argument("--max-detail-links", type=int, default=200, help="Max detail links to discover.")
    parser_discover.add_argument("--timeout", type=float, default=45.0, help="Request timeout in seconds.")
    parser_discover.set_defaults(func=lambda args: asyncio.run(run_discovery(args)))

    # Subcommand: run
    parser_run = subparsers.add_parser("run", help="Run ingestion for a site.")
    parser_run.add_argument("base_url", help="The base URL of the site to ingest.")
    parser_run.add_argument("--tenant-id", type=int, default=101, help="Tenant ID to use.")
    parser_run.add_argument("--max-listings", type=int, default=30, help="Max listings to process.")
    parser_run.add_argument("--max-listing-pages", type=int, default=5, help="Max listing pages to crawl.")
    parser_run.add_argument("--timeout", type=float, default=45.0, help="Request timeout in seconds per request.")
    parser_run.set_defaults(func=lambda args: asyncio.run(run_ingestion(args)))

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

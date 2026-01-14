from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from lxml import etree


@dataclass(frozen=True)
class DiscoveryResult:
    base_url: str
    domain: str
    sitemaps: list[str]
    listing_candidates: list[str]
    detail_candidates: list[str]


def _normalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = p.scheme.lower() or "https"
    netloc = p.netloc.lower()
    path = p.path or "/"
    return f"{scheme}://{netloc}{path}".rstrip("/")


_LISTING_HINTS = [
    "estoque",
    "veiculos",
    "veículos",
    "carros",
    "seminovos",
    "semi-novos",
    "vitrine",
    "catalogo",
    "catálogo",
]

_DETAIL_HINTS = [
    "veiculo",
    "veículo",
    "carro",
    "anuncio",
    "anúncio",
    "detalhe",
]

_NEGATIVE_HINTS = [
    "contato",
    "sobre",
    "politica",
    "política",
    "privacidade",
    "termos",
    "login",
    "admin",
    "wp-admin",
    "blog",
]


def _normalize_base_url(base_url: str) -> str:
    s = (base_url or "").strip()
    if not s:
        raise ValueError("missing_base_url")
    if not re.match(r"^https?://", s, flags=re.IGNORECASE):
        s = "https://" + s
    return s.rstrip("/")


def _same_domain(url: str, domain: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == domain.lower()
    except Exception:
        return False


def _score_link(path: str) -> int:
    tl = (path or "").lower()
    if any(h in tl for h in _NEGATIVE_HINTS):
        return -100
    score = 0
    if any(h in tl for h in _LISTING_HINTS):
        score += 10
    if any(h in tl for h in _DETAIL_HINTS):
        score += 6
    if re.search(r"\b(page|pagina|pag|p)=\d+", tl):
        score += 3
    if re.search(r"\b(id|codigo|cod)=\d+", tl):
        score += 5
    return score


def _extract_links_from_html(*, html: str, base: str, domain: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    out: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        abs_url = urljoin(base + "/", href)
        if not _same_domain(abs_url, domain):
            continue
        out.add(_normalize_url(abs_url))
    return list(out)


def _looks_like_detail(url: str) -> bool:
    tl = (url or "").lower()
    if any(h in tl for h in _NEGATIVE_HINTS):
        return False
    if any(h in tl for h in _DETAIL_HINTS):
        return True
    return bool(re.search(r"\b(19[8-9]\d|20[0-3]\d)\b", tl))


def _looks_like_listing(url: str) -> bool:
    tl = (url or "").lower()
    if any(h in tl for h in _NEGATIVE_HINTS):
        return False
    if any(h in tl for h in _LISTING_HINTS):
        return True
    return False


async def _crawl_listing_pages(
    *,
    client: httpx.AsyncClient,
    start_urls: list[str],
    base: str,
    domain: str,
    max_pages: int,
    max_detail_links: int,
) -> tuple[set[str], set[str]]:
    visited: set[str] = set()
    queue: list[str] = []
    for u in start_urls:
        if u:
            queue.append(u)

    listing_found: set[str] = set()
    detail_found: set[str] = set()

    while queue and len(visited) < max_pages and len(detail_found) < max_detail_links:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            r = await client.get(url)
            if r.status_code >= 400:
                continue
            html = r.text or ""
        except Exception:
            continue

        links = _extract_links_from_html(html=html, base=base, domain=domain)
        for lk in links:
            if _looks_like_detail(lk) and len(detail_found) < max_detail_links:
                detail_found.add(lk)
            if _looks_like_listing(lk):
                listing_found.add(lk)
                if lk not in visited and lk not in queue and len(visited) + len(queue) < max_pages:
                    queue.append(lk)

    return listing_found, detail_found


async def discover_site(
    *,
    base_url: str,
    timeout_seconds: float = 10.0,
    max_listing_pages: int = 4,
    max_detail_links: int = 400,
) -> DiscoveryResult:
    base = _normalize_base_url(base_url)
    domain = urlparse(base).netloc

    sitemaps: list[str] = []
    listing_candidates: set[str] = set()
    detail_candidates: set[str] = set()

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        robots_url = urljoin(base + "/", "robots.txt")
        try:
            r = await client.get(robots_url)
            if r.status_code < 400:
                for line in (r.text or "").splitlines():
                    m = re.match(r"(?i)^sitemap:\s*(.+)$", line.strip())
                    if m:
                        sitemaps.append(m.group(1).strip())
        except Exception:
            pass

        for cand in ["/sitemap.xml", "/sitemap_index.xml"]:
            u = base + cand
            if u not in sitemaps:
                sitemaps.append(u)

        # Parse sitemaps
        sitemap_urls: set[str] = set()
        for sm in list(dict.fromkeys(sitemaps)):
            try:
                r = await client.get(sm)
                if r.status_code >= 400:
                    continue
                content = (r.content or b"")
                if not content:
                    continue
                root = etree.fromstring(content)
                locs = root.findall(".//{*}loc")
                for loc in locs:
                    if loc.text:
                        sitemap_urls.add(loc.text.strip())
            except Exception:
                continue

        for u in sitemap_urls:
            if not _same_domain(u, domain):
                continue
            norm = _normalize_url(u)
            tl = norm.lower()
            if any(h in tl for h in _NEGATIVE_HINTS):
                continue
            if any(h in tl for h in _LISTING_HINTS):
                listing_candidates.add(norm)
            if any(h in tl for h in _DETAIL_HINTS) or re.search(r"\b\d{4}\b", tl):
                detail_candidates.add(norm)

        # Crawl home for candidate links
        try:
            r = await client.get(base)
            if r.status_code < 400:
                soup = BeautifulSoup(r.text or "", "lxml")
                for a in soup.find_all("a", href=True):
                    href = (a.get("href") or "").strip()
                    if not href or href.startswith("#"):
                        continue
                    abs_url = urljoin(base + "/", href)
                    if not _same_domain(abs_url, domain):
                        continue
                    norm = _normalize_url(abs_url)
                    score = _score_link(urlparse(norm).path + ("?" + urlparse(abs_url).query if urlparse(abs_url).query else ""))
                    if score < 0:
                        continue
                    tl = norm.lower()
                    if any(h in tl for h in _LISTING_HINTS):
                        listing_candidates.add(norm)
                    if any(h in tl for h in _DETAIL_HINTS):
                        detail_candidates.add(norm)
        except Exception:
            pass

        # Crawl listing candidates to find detail links (reduz dependência de sitemap/home)
        if max_listing_pages > 0 and max_detail_links > 0 and listing_candidates:
            try:
                listing_found, detail_found = await _crawl_listing_pages(
                    client=client,
                    start_urls=sorted(list(listing_candidates))[:10],
                    base=base,
                    domain=domain,
                    max_pages=int(max_listing_pages),
                    max_detail_links=int(max_detail_links),
                )
                for u in listing_found:
                    listing_candidates.add(u)
                for u in detail_found:
                    detail_candidates.add(u)
            except Exception:
                pass

    return DiscoveryResult(
        base_url=base,
        domain=domain,
        sitemaps=list(dict.fromkeys(sitemaps)),
        listing_candidates=sorted(list(listing_candidates))[:50],
        detail_candidates=sorted(list(detail_candidates))[:200],
    )

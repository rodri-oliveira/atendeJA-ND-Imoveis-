from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class VehicleListing:
    url: str
    title: str | None
    description: str | None
    price: float | None
    year: int | None
    km: int | None
    make: str | None
    model: str | None
    transmission: str | None
    fuel: str | None
    images: list[str]


def normalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    path = p.path or "/"
    return f"{scheme}://{netloc}{path}".rstrip("/")


def external_key_from_url(url: str) -> str:
    norm = normalize_url(url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _parse_price(text: str) -> float | None:
    t = (text or "").strip()
    if not t:
        return None
    n = re.sub(r"[^0-9,\.]", "", t).replace(".", "").replace(",", ".")
    try:
        v = float(n)
        if v <= 0:
            return None
        return v
    except Exception:
        return None


def _parse_int(text: str) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    n = re.sub(r"[^0-9]", "", t)
    try:
        return int(n)
    except Exception:
        return None


def _extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (s.string or s.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend([d for d in data if isinstance(d, dict)])
        except Exception:
            continue
    return out


def parse_vehicle_listing(*, html: str, page_url: str) -> VehicleListing:
    soup = BeautifulSoup(html or "", "lxml")

    title: str | None = None
    description: str | None = None
    price: float | None = None
    year: int | None = None
    km: int | None = None
    make: str | None = None
    model: str | None = None
    transmission: str | None = None
    fuel: str | None = None
    images: list[str] = []

    # Layer 1: JSON-LD
    for doc in _extract_json_ld(soup):
        t = doc.get("@type")
        if isinstance(t, list):
            t = t[0] if t else None
        t = str(t).lower() if t else ""

        if t in {"product", "vehicle", "car"}:
            title = title or doc.get("name")
            description = description or doc.get("description")

            img = doc.get("image")
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, list):
                images.extend([x for x in img if isinstance(x, str)])

            offers = doc.get("offers")
            if isinstance(offers, dict):
                price = price or _parse_price(str(offers.get("price") or ""))

            brand = doc.get("brand")
            if isinstance(brand, dict):
                make = make or brand.get("name")

            model = model or doc.get("model")
            break

    # Layer 1.5: OpenGraph/meta
    if not title:
        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"):
            title = ogt.get("content")
    if not images:
        ogi = soup.find("meta", property="og:image")
        if ogi and ogi.get("content"):
            images.append(ogi.get("content"))

    # Layer 2: Heuristics
    text = soup.get_text(" ", strip=True)

    if price is None:
        m = re.search(r"R\$\s*[0-9\.]+(?:,[0-9]{2})?", text)
        if m:
            price = _parse_price(m.group(0))

    if year is None:
        m = re.search(r"\b(19[8-9]\d|20[0-3]\d)\b", text)
        if m:
            year = _parse_int(m.group(0))

    if km is None:
        m = re.search(r"([0-9\.]{1,12})\s*km\b", text.lower())
        if m:
            km = _parse_int(m.group(1))

    tl = text.lower()
    if transmission is None:
        if "autom" in tl:
            transmission = "automatic"
        elif "manual" in tl:
            transmission = "manual"

    if fuel is None:
        if "flex" in tl:
            fuel = "flex"
        elif "diesel" in tl:
            fuel = "diesel"
        elif "gasolina" in tl:
            fuel = "gasoline"
        elif "etanol" in tl:
            fuel = "ethanol"

    # Layer 2.5: title-derived make/model
    if title and (make is None or model is None):
        # naive split: "Marca Modelo ..."
        parts = re.split(r"\s+", title.strip())
        if len(parts) >= 2:
            make = make or parts[0]
            model = model or parts[1]

    images = [i for i in images if i]
    if images:
        # remove duplicates preserving order
        dedup: list[str] = []
        seen: set[str] = set()
        for u in images:
            if u in seen:
                continue
            seen.add(u)
            dedup.append(u)
        images = dedup[:15]

    return VehicleListing(
        url=page_url,
        title=title,
        description=description,
        price=price,
        year=year,
        km=km,
        make=make,
        model=model,
        transmission=transmission,
        fuel=fuel,
        images=images,
    )

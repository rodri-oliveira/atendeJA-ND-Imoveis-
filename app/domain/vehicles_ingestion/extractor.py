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
    accessories: list[str]


def normalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    path = p.path or "/"
    return f"{scheme}://{netloc}{path}".rstrip("/")


def external_key_from_url(url: str) -> str:
    norm = normalize_url(url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _is_probably_vehicle_photo(url: str) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    lu = u.lower()
    if lu.startswith("data:"):
        return False
    try:
        p = urlparse(lu)
        path = (p.path or "").lower()
    except Exception:
        path = lu

    # Exclude obvious non-photos / branding assets
    if path.endswith((".svg", ".ico")):
        return False
    if any(k in path for k in [
        "favicon",
        "logo",
        "brand",
        "sprite",
        "icon",
        "header",
        "footer",
        "navbar",
        "menu",
        "social",
        "whatsapp",
        "facebook",
        "instagram",
        "tiktok",
        "placeholder",
        "noimage",
        "default",
        "banner",
    ]):
        return False

    return True


def _extract_accessories(soup: BeautifulSoup) -> list[str]:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    out: list[str] = []

    # Prefer explicit section titled "Acessórios" (ClickGarage renders it like that)
    section_title = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        txt = norm(tag.get_text(" ", strip=True))
        if not txt:
            continue
        lt = txt.lower()
        if "acess" in lt:
            section_title = tag
            break

    if section_title is not None:
        lst = section_title.find_next(["ul", "ol"])
        if lst is not None:
            for li in lst.find_all("li", limit=120):
                t = norm(li.get_text(" ", strip=True))
                if not t:
                    continue
                if len(t) > 80:
                    continue
                out.append(t)

    # Dedup preserving order
    dedup: list[str] = []
    seen: set[str] = set()
    for x in out:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(x)
    return dedup[:40]


def _parse_price(text: str) -> float | None:
    t = (text or "").strip()
    if not t:
        return None

    # Robust BR formats:
    # - "99.900,00" (thousand='.', decimal=',')
    # - "99,900,00" (thousand=',', decimal=',')
    # - "99900" / "99900.00"
    raw = re.sub(r"[^0-9,\.]", "", t)
    if not raw:
        return None

    # If both separators exist, decide decimal separator by last occurrence.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            # decimal is ',' -> remove '.' thousand sep and normalize last ',' to '.'
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            # decimal is '.' -> remove ',' thousand sep
            raw = raw.replace(",", "")
    elif raw.count(",") >= 2 and "." not in raw:
        # e.g. "216,900,00" -> keep last ',' as decimal
        parts = raw.split(",")
        dec = parts[-1]
        intp = "".join(parts[:-1])
        raw = f"{intp}.{dec}"
    elif raw.count(",") == 1 and "." not in raw:
        # e.g. "99900,00" or "99900,0"
        raw = raw.replace(",", ".")

    n = raw
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
    accessories: list[str] = []

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

    if title:
        # Normalize common noisy prefixes like "Veiculo -" (including unicode dashes)
        title = (
            re.sub(
                r"^\s*(ve[ií]culo|carro)\s*[-:\u2013\u2014]+\s*",
                "",
                str(title),
                flags=re.IGNORECASE,
            )
            .strip()
            or title
        )

    if not description:
        ogd = soup.find("meta", property="og:description")
        if ogd and ogd.get("content"):
            description = str(ogd.get("content") or "").strip() or description
    if not description:
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            description = str(md.get("content") or "").strip() or description

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

    # ClickGarage-like labels (common in car dealer sites)
    if km is None:
        m = re.search(r"quilometragem\s*([0-9\.]{1,12})\b", text, flags=re.IGNORECASE)
        if m:
            km = _parse_int(m.group(1))

    if year is None:
        # Ex: "Ano/Modelo 2023 / 2023"
        m = re.search(r"ano\s*/\s*modelo\s*([12][0-9]{3})", text, flags=re.IGNORECASE)
        if m:
            year = _parse_int(m.group(1))
        if year is None:
            m = re.search(r"ano\s*/\s*modelo\s*([12][0-9]{3})\s*/\s*([12][0-9]{3})", text, flags=re.IGNORECASE)
            if m:
                year = _parse_int(m.group(1))

    if transmission is None:
        # Ex: "Câmbio AUTOMÁTICO"
        m = re.search(r"c[âa]mbio\s*([a-z\s]{3,20})", text, flags=re.IGNORECASE)
        if m:
            v = (m.group(1) or "").strip().lower()
            if "auto" in v:
                transmission = "automatic"
            elif "man" in v:
                transmission = "manual"

    if fuel is None:
        m = re.search(r"combust[ií]vel\s*([a-z\s]{3,20})", text, flags=re.IGNORECASE)
        if m:
            v = (m.group(1) or "").strip().lower()
            if "flex" in v:
                fuel = "flex"
            elif "diesel" in v:
                fuel = "diesel"
            elif "gasolina" in v:
                fuel = "gasoline"
            elif "etanol" in v:
                fuel = "ethanol"

    if price is None:
        matches = re.findall(r"R\$\s*[0-9\.,]{1,16}", text)
        candidates: list[float] = []
        for raw in matches:
            v = _parse_price(raw)
            if v is None:
                continue
            if v < 1000:
                continue
            candidates.append(v)
        if candidates:
            price = max(candidates)

    if year is None:
        m = re.search(r"\b(19[8-9]\d|20[0-3]\d)\b", text)
        if m:
            year = _parse_int(m.group(0))

    if km is None:
        kms = re.findall(r"([0-9\.]{1,12})\s*km\b", text.lower())
        km_candidates: list[int] = []
        for raw in kms:
            v = _parse_int(raw)
            if v is None:
                continue
            if v <= 0:
                continue
            km_candidates.append(v)
        if km_candidates:
            km = max(km_candidates)

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
        # naive split: "Marca Modelo ..." with common noisy prefixes
        parts = [p for p in re.split(r"\s+", title.strip()) if p and p not in {"-", "–", "—"}]
        if parts and parts[0].lower() in {"veiculo", "veículo", "carro"}:
            parts = parts[1:]
        if len(parts) >= 2:
            cand_make = parts[0]
            cand_model = parts[1]
            if cand_make.lower() in {"veiculo", "veículo", "carro"}:
                cand_make = ""
            if cand_model in {"-", "–", "—"}:
                cand_model = ""
            make = make or (cand_make or None)
            model = model or (cand_model or None)

    # Guardrails: never keep invalid placeholders
    if make and make.strip().lower() in {"veiculo", "veículo", "carro", "-"}:
        make = None
    if model and model.strip() in {"-", "–", "—"}:
        model = None

    images = [i for i in images if i]
    images = [i for i in images if _is_probably_vehicle_photo(str(i))]
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

    if not images:
        img_urls: list[str] = []
        for img in soup.find_all("img"):
            u = img.get("data-src") or img.get("data-original") or img.get("src")
            if not u:
                continue
            u = str(u).strip()
            if not u:
                continue
            if not _is_probably_vehicle_photo(u):
                continue
            img_urls.append(u)
        if img_urls:
            dedup: list[str] = []
            seen: set[str] = set()
            for u in img_urls:
                if u in seen:
                    continue
                seen.add(u)
                dedup.append(u)
            images = dedup[:15]

    accessories = _extract_accessories(soup)

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
        accessories=accessories,
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal
from urllib.parse import urljoin
import re
import json
import httpx
from bs4 import BeautifulSoup
import structlog

# Em desenvolvimento, usamos http para evitar problemas de cadeia SSL no Windows.
ND_BASE = "http://www.ndimoveis.com.br"
UA = {"User-Agent": "AtendeJA-Bot/1.0"}
log = structlog.get_logger()


@dataclass
class PropertyDTO:
    url: str
    external_id: str | None
    title: str | None
    price: float | None
    purpose: Literal["sale", "rent", None]
    ptype: Literal["apartment", "house", "commercial", "land", None]
    address: str | None
    city: str | None
    state: str | None
    neighborhood: str | None
    bedrooms: int | None
    bathrooms: int | None
    suites: int | None
    parking: int | None
    area_total: float | None
    condo_fee: float | None
    iptu: float | None
    images: list[str]


def _parse_money(text: str | None) -> float | None:
    if not text:
        return None
    s = str(text)
    n = re.sub(r"[^0-9,\.]", "", s).replace(".", "").replace(",", ".")
    try:
        return float(n)
    except Exception:
        return None


def _normalize_money_text(raw: str | None) -> float | None:
    """Converte textos como 'R$ 219,9 mil' ou 'R$ 1,2 milhão' em números absolutos."""
    if not raw:
        return None
    txt = str(raw)
    # Sinalizar sufixos
    lower = txt.lower()
    mult = 1.0
    # milhão/milhões/mi
    if re.search(r"milh(ão|ao|oes|ões)|\bmi\b", lower, flags=re.IGNORECASE):
        mult = 1_000_000.0
    # mil
    elif re.search(r"\bmil\b", lower, flags=re.IGNORECASE):
        mult = 1_000.0
    # Capturar parte numérica
    m = re.search(r"([0-9]{1,3}(?:\.[0-9]{3})*|[0-9]+)(?:,[0-9]{1,3})?", lower)
    if not m:
        # fallback: usa _parse_money direto
        return _parse_money(lower)
    num_txt = m.group(0)
    base = _parse_money(num_txt)
    if base is None:
        return None
    return base * mult


def list_url_candidates(finalidade: str, page: int) -> list[str]:
    # Padrões observados no site (pager usa 'pag' e mantém 'pagina=1')
    if finalidade == "venda":
        return [
            f"{ND_BASE}/imovel/venda/?pagina=1&pag={page}",
            f"{ND_BASE}/imovel/venda/?pag={page}",
            # Fallbacks
            f"{ND_BASE}/imovel/venda?page={page}",
            f"{ND_BASE}/imovel/?finalidade=venda&pag={page}",
            f"{ND_BASE}/imovel/?finalidade=venda&pagina={page}",
            f"{ND_BASE}/imovel/?finalidade=venda&page={page}",
            f"{ND_BASE}/imovel/venda",
            f"{ND_BASE}/imovel/?finalidade=venda",
        ]
    if finalidade == "locacao":
        return [
            f"{ND_BASE}/imovel/locacao/?pagina=1&pag={page}",
            f"{ND_BASE}/imovel/locacao/?pag={page}",
            # Fallbacks
            f"{ND_BASE}/imovel/locacao?page={page}",
            f"{ND_BASE}/imovel/?finalidade=locacao&pag={page}",
            f"{ND_BASE}/imovel/?finalidade=locacao&pagina={page}",
            f"{ND_BASE}/imovel/?finalidade=locacao&page={page}",
            f"{ND_BASE}/imovel/locacao",
            f"{ND_BASE}/imovel/?finalidade=locacao",
        ]
    return [
        f"{ND_BASE}/imovel/?pagina={page}",
        f"{ND_BASE}/imovel/?page={page}",
        f"{ND_BASE}/imovel/?pag={page}",
        f"{ND_BASE}/imovel/",
    ]


def discover_list_links(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.search(r"/imovel/\d+/[a-z0-9\-]+", href, flags=re.IGNORECASE):
            links.add(urljoin(ND_BASE, href))
    return sorted(links)


def parse_detail(html: str, page_url: str) -> PropertyDTO:
    soup = BeautifulSoup(html or "", "lxml")

    def txt(el) -> str | None:
        if not el:
            return None
        t = el.get_text(" ", strip=True)
        return t if t else None

    # title
    h1 = soup.find("h1")
    title = txt(h1)

    # external id (ex.: Código: A1234). Tentar múltiplos locais e, se não achar, fallback pela URL.
    ext = None
    # 1) Qualquer nó de texto que contenha 'Código'
    code_el = soup.find(string=re.compile(r"Código", re.IGNORECASE))
    if code_el:
        m = re.search(r"([A-Za-z]\d{2,})", str(code_el))
        if m:
            ext = m.group(1)
    # 2) Buscar também em labels ao lado
    if not ext:
        labels = soup.find_all(string=re.compile(r"Código", re.IGNORECASE))
        for lab in labels:
            parent_text = lab.parent.get_text(" ", strip=True) if lab and lab.parent else None
            if parent_text:
                m2 = re.search(r"([A-Za-z]\d{2,})", parent_text)
                if m2:
                    ext = m2.group(1)
                    break
    # 3) Fallback: extrair id numérico da URL /imovel/123456/...
    if not ext:
        murl = re.search(r"/imovel/(\d+)/", page_url)
        if murl:
            ext = murl.group(1)

    # price: priorizar JSON-LD, seletores de preço e evitar taxas (Condomínio/IPTU). Escolher o maior valor confiável.
    price = None
    candidates: list[str] = []
    # 0) JSON-LD (schema.org)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
        except Exception:
            continue
        def extract_prices(obj):
            vals = []
            if isinstance(obj, dict):
                # offers pode ser dict ou lista
                if "offers" in obj:
                    offers = obj.get("offers")
                    if isinstance(offers, list):
                        for off in offers:
                            if isinstance(off, dict):
                                if "price" in off and off.get("price") is not None:
                                    vals.append(str(off["price"]))
                                if "lowPrice" in off:
                                    vals.append(str(off["lowPrice"]))
                                if "highPrice" in off:
                                    vals.append(str(off["highPrice"]))
                    elif isinstance(offers, dict):
                        if "price" in offers and offers.get("price") is not None:
                            vals.append(str(offers["price"]))
                        if "lowPrice" in offers:
                            vals.append(str(offers["lowPrice"]))
                        if "highPrice" in offers:
                            vals.append(str(offers["highPrice"]))
                # fallback: campos diretos
                if "price" in obj and obj.get("price") is not None:
                    vals.append(str(obj["price"]))
            elif isinstance(obj, list):
                for it in obj:
                    vals.extend(extract_prices(it))
            return vals
        candidates.extend(extract_prices(data))
    # 1) itemprop="price" (meta/span)
    price_nodes = []
    price_nodes.extend(soup.select('[itemprop="price"]'))
    meta_price = soup.select('meta[itemprop="price"][content]')
    for mp in meta_price:
        val = mp.get('content')
        if val:
            candidates.append(val)
    for node in price_nodes:
        t = node.get_text(" ", strip=True)
        if t:
            candidates.append(t)
    # 2) classes comuns de preço
    for cls in ["preco", "price", "valor", "price-value", "preco-principal"]:
        for el in soup.select(f'.{cls}'):
            t = el.get_text(" ", strip=True)
            if t:
                candidates.append(t)
    # 3) fallback: qualquer R$ no documento
    for stext in soup.find_all(string=re.compile(r"R\$\s*")):
        t = str(stext)
        if t:
            candidates.append(t)
    # filtrar taxas
    filtered: list[float] = []
    for c in candidates:
        if re.search(r"condom[ií]nio|iptu", c, flags=re.IGNORECASE):
            continue
        val = _normalize_money_text(c)
        if val is not None and val > 0:
            filtered.append(val)
    if filtered:
        price = max(filtered)

    # purpose and type (priorizar locação)
    purpose = None
    body_text = soup.get_text(" ", strip=True)
    title_lower = (title or "").lower()
    # 1) Título é mais confiável
    if re.search(r"loca[cç][aã]o|alug", title_lower):
        purpose = "rent"
    elif re.search(r"venda", title_lower):
        purpose = "sale"
    # 2) Fallback: corpo do documento
    if purpose is None:
        if re.search(r"Loca[cç][aã]o|Aluguel", body_text, re.IGNORECASE):
            purpose = "rent"
        elif re.search(r"\bVenda\b", body_text, re.IGNORECASE):
            purpose = "sale"

    ptype = None
    bt = body_text
    if re.search(r"Apartamento", bt, re.IGNORECASE):
        ptype = "apartment"
    elif re.search(r"Casa|Sobrado", bt, re.IGNORECASE):
        ptype = "house"
    elif re.search(r"Sala|Comercial", bt, re.IGNORECASE):
        ptype = "commercial"
    elif re.search(r"Terreno|Lote", bt, re.IGNORECASE):
        ptype = "land"

    # address / neighborhood / city-state
    address = None
    neighborhood = None
    city = None
    state = None

    # Tentativas: procurar labels comuns
    def after_label(label_regex: str) -> str | None:
        lab = soup.find(string=re.compile(label_regex, re.IGNORECASE))
        if lab and lab.parent:
            # pegar o texto do próximo irmão ou do pai
            sib = lab.find_parent()
            if sib:
                t = sib.get_text(" ", strip=True)
                # remove o label
                t = re.sub(label_regex + r"\s*:?", "", t, flags=re.IGNORECASE)
                return t.strip() or None
        return None

    neighborhood = after_label(r"Bairro") or neighborhood
    address = after_label(r"Endere[cç]o|Endereço") or address

    # city/state a partir do título
    if title:
        m = re.search(r",\s*([^/]+)\s*/\s*([A-Z]{2})", title)
        if m:
            city = m.group(1).strip()
            state = m.group(2).strip()

    # numbers (bedrooms/suites/bathrooms/parking/area)
    def find_num(pattern: str) -> int | None:
        m = re.search(pattern, body_text, flags=re.IGNORECASE)
        if not m:
            return None
        m2 = re.search(r"(\d+)", m.group(0))
        return int(m2.group(1)) if m2 else None

    bedrooms = find_num(r"\b\d+\s*Dormit[óo]rios?")
    suites = find_num(r"\b\d+\s*Su[ií]tes?")
    bathrooms = find_num(r"\b\d+\s*Banheiros?")
    parking = find_num(r"\b\d+\s*(Vagas?|Garagem)")

    area_total = None
    m_area = re.search(r"(\d{1,4}[\.,]\d{1,2}|\d{1,4})\s*m²", body_text, flags=re.IGNORECASE)
    if m_area:
        area_total = _parse_money(m_area.group(1))

    # condo fee / iptu
    condo_fee = None
    iptu = None
    m_c = re.search(r"Condom[ií]nio\s*:\s*([^\n<]+)", body_text, re.IGNORECASE)
    if m_c:
        condo_fee = _parse_money(m_c.group(1))
    m_i = re.search(r"IPTU\s*:\s*([^\n<]+)", body_text, re.IGNORECASE)
    if m_i:
        iptu = _parse_money(m_i.group(1))

    # images - filtrar apenas imagens da galeria do imóvel
    images: list[str] = []
    all_imgs = soup.find_all("img", src=True)
    for img in all_imgs:
        src = img["src"].strip()
        full_url = urljoin(ND_BASE, src)
        
        # Aceitar apenas URLs do CDN de imóveis (cdn-imobibrasil)
        if "cdn-imobibrasil.com.br/imagens/imoveis/" in full_url:
            images.append(full_url)
        # Fallback: aceitar imagens em diretórios específicos de upload/galeria (excluir logos/layout)
        elif re.search(r"/(upload|galeria|fotos?)/.*\.(jpe?g|png|webp)", full_url, re.IGNORECASE):
            # Excluir imagens de layout/site
            if not re.search(r"(logo|icon|banner|site_modelo|imagensct|redesp_|whatsapp_modulo)", full_url, re.IGNORECASE):
                images.append(full_url)
    # Log resumido
    try:
        log.info("nd_parse_images", total_all=len(all_imgs), accepted=len(images))
    except Exception:
        pass

    return PropertyDTO(
        url=page_url,
        external_id=ext,
        title=title,
        price=price,
        purpose=purpose,  # type: ignore
        ptype=ptype,      # type: ignore
        address=address,
        city=city,
        state=state,
        neighborhood=neighborhood,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        suites=suites,
        parking=parking,
        area_total=area_total,
        condo_fee=condo_fee,
        iptu=iptu,
        images=images,
    )

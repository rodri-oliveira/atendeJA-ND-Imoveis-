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
    description: str | None
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

    # description (longa): tentar capturar a seção "Descrição do Imóvel"; fallback para bloco textual principal
    description: str | None = None
    try:
        # 1) Procurar seção com o texto "Descrição do Imóvel"
        desc_header = None
        # 1a) Primeiro, em headings h1..h6
        for tag in soup.find_all(re.compile(r'^h[1-6]$')):
            t = tag.get_text(" ", strip=True)
            if re.search(r"Descri[cç][aã]o\s+do\s+Im[óo]vel", t, flags=re.IGNORECASE):
                desc_header = tag
                break
        # 1b) Se não achou em heading, aceitar qualquer nó que contenha o rótulo
        if not desc_header:
            any_label = soup.find(string=re.compile(r"Descri[cç][aã]o\s+do\s+Im[óo]vel", re.IGNORECASE))
            if any_label and getattr(any_label, 'parent', None):
                desc_header = any_label.parent

        collected: list[str] = []
        collected_len = 0

        def push_text(s: str):
            nonlocal collected_len
            s2 = (s or "").strip()
            if not s2:
                return
            collected.append(s2)
            collected_len += len(s2)

        stop_re = re.compile(r"Central de Neg[oó]cios|Fale agora|Galeria|Características|Proximidades|Cômodos|Mapa de Localiza[çc][aã]o", re.IGNORECASE)

        if desc_header:
            # 2) Varrer elementos seguintes (inclui nós aninhados) até próxima seção
            for el in getattr(desc_header, 'next_elements', []):
                # Parar em um heading H1/H2 que não seja a própria descrição
                if getattr(el, 'name', None) and re.match(r'^h[1-2]$', el.name):
                    try:
                        htext = el.get_text(" ", strip=True)
                    except Exception:
                        htext = ""
                    if htext and not re.search(r"Descri[cç][aã]o\s+do\s+Im[óo]vel", htext, flags=re.IGNORECASE):
                        break
                # Texto do elemento atual
                try:
                    el_text = getattr(el, 'get_text', lambda *a, **k: "")(" ", strip=True)
                except Exception:
                    el_text = ""
                if el_text and stop_re.search(el_text):
                    break
                # Listas
                if getattr(el, 'name', None) in ('ul', 'ol'):
                    try:
                        for li in el.find_all('li'):
                            li_txt = li.get_text(" ", strip=True)
                            if li_txt:
                                push_text(li_txt)
                    except Exception:
                        pass
                if el_text:
                    push_text(el_text)
                if collected_len >= 3000:
                    break
        else:
            # 3) Fallback: pega parágrafos e também itens de lista relevantes
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all('p')]
            list_items = [li.get_text(" ", strip=True) for li in soup.find_all('li')]
            # Manter apenas textos medianos/grandes e evitar seções de parada
            for ptxt in paragraphs:
                if 60 <= len(ptxt) <= 800 and not stop_re.search(ptxt):
                    push_text(ptxt)
                if collected_len >= 3000:
                    break
            if collected_len < 300:  # ainda curto: complementar com itens de lista
                for ltxt in list_items:
                    if 20 <= len(ltxt) <= 400 and not stop_re.search(ltxt):
                        push_text(ltxt)
                    if collected_len >= 3000:
                        break

        # Normalizações leves
        joined = "\n".join(collected).strip()
        if joined:
            joined = re.sub(r"\s*\n\s*", "\n", joined)
            joined = re.sub(r"\n{3,}", "\n\n", joined)
            description = joined[:3000]
        # Fallback adicional: se descrição inexistente ou muito curta, usar meta tags e parágrafos globais
        def _ensure_min_desc(existing: str | None) -> str | None:
            try:
                cur = (existing or "").strip()
                if len(cur) >= 150:
                    return cur
                # 1) OG/meta description
                metas = []
                for sel in [
                    'meta[name="description"][content]',
                    'meta[property="og:description"][content]',
                    'meta[name="og:description"][content]'
                ]:
                    for m in soup.select(sel):
                        c = (m.get('content') or '').strip()
                        if c and c.lower() != 'imóveis disponíveis':
                            metas.append(c)
                # 2) Global paragraphs/list items (filtrando stop words)
                paras = [p.get_text(" ", strip=True) for p in soup.find_all('p') if p]
                lis = [li.get_text(" ", strip=True) for li in soup.find_all('li') if li]
                parts: list[str] = []
                # Prioriza meta
                for t in metas:
                    if 40 <= len(t) <= 400 and not stop_re.search(t):
                        parts.append(t)
                # Parágrafos
                for t in paras:
                    if 60 <= len(t) <= 800 and not stop_re.search(t):
                        parts.append(t)
                        if sum(len(x) for x in parts) >= 1200:
                            break
                # Complementa com listas
                if sum(len(x) for x in parts) < 300:
                    for t in lis:
                        if 30 <= len(t) <= 400 and not stop_re.search(t):
                            parts.append(t)
                            if sum(len(x) for x in parts) >= 1200:
                                break
                text = "\n".join(parts).strip()
                if text:
                    text = re.sub(r"\s*\n\s*", "\n", text)
                    text = re.sub(r"\n{3,}", "\n\n", text)
                return (text[:3000] if text else (cur or None))
            except Exception:
                return existing
        description = _ensure_min_desc(description)
    except Exception:
        description = None

    # external id (ex.: Código: A1234 ou Ref: A1234, também aceita 'A-1234' e 'A 1234').
    # Tentar múltiplos locais e, se não achar, fallback pela URL.
    def _extract_ext(text: str | None) -> str | None:
        if not text:
            return None
        try:
            m = re.search(r"([A-Za-z])[\s\-]?(\d{2,})", text)
            if m:
                # Normaliza removendo separadores: 'A-1275' -> 'A1275'
                return (m.group(1).upper() + m.group(2))
        except Exception:
            return None
        return None
    ext = None
    # 1) Qualquer nó de texto que contenha 'Código'
    code_el = soup.find(string=re.compile(r"Código", re.IGNORECASE))
    if code_el:
        ext_try = _extract_ext(str(code_el))
        if ext_try:
            ext = ext_try
    # 2) Buscar também em labels ao lado
    if not ext:
        labels = soup.find_all(string=re.compile(r"Código", re.IGNORECASE))
        for lab in labels:
            parent_text = lab.parent.get_text(" ", strip=True) if lab and lab.parent else None
            if parent_text:
                ext_try2 = _extract_ext(parent_text)
                if ext_try2:
                    ext = ext_try2
                    break
    # 2b) Procurar padrões 'Ref' / 'Referência'
    if not ext:
        # Busca direta por strings contendo 'Ref' ou 'Referência'
        ref_nodes = soup.find_all(string=re.compile(r"Ref|Refer[eê]ncia", re.IGNORECASE))
        for rn in ref_nodes:
            try:
                txtn = rn.parent.get_text(" ", strip=True) if rn and rn.parent else str(rn)
            except Exception:
                txtn = str(rn)
            ext_try3 = _extract_ext(txtn)
            if ext_try3:
                ext = ext_try3
                break
    # 2c) Varredura de corpo completo como último recurso textual (antes do fallback de URL)
    if not ext:
        body_full = soup.get_text(" ", strip=True)
        ext_try4 = _extract_ext(body_full)
        if ext_try4:
            ext = ext_try4
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
        description=description,
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

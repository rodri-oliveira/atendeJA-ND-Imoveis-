"""
Funções de detecção de intenção usando LLM (substituição de detection_utils.py).
Mantém a mesma interface para compatibilidade com conversation_handlers.py.
VERSÃO: 2024-10-16 14:28 - Fallback robusto para valores por extenso
"""
from typing import Optional
import asyncio
from app.services.llm_service import get_llm_service
import structlog

log = structlog.get_logger()


def detect_consent(text: str) -> bool:
    """Detecta consentimento LGPD via LLM."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        return result.get("intent") == "responder_lgpd"
    except:
        # Fallback para regex simples
        text_lower = text.lower().strip()
        return any(kw in text_lower for kw in ["sim", "autorizo", "aceito", "ok", "concordo"])


def detect_purpose(text: str) -> Optional[str]:
    """Detecta finalidade (rent/sale) via LLM."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        return result.get("entities", {}).get("finalidade")
    except:
        # Fallback para regex
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["alugar", "aluguel", "locação", "locar"]):
            return "rent"
        if any(kw in text_lower for kw in ["comprar", "compra", "venda", "vender"]):
            return "sale"
        return None


def detect_property_type(text: str) -> Optional[str]:
    """Detecta tipo de imóvel (house/apartment/commercial/land) via LLM."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        prop_type = result.get("entities", {}).get("tipo")
        if prop_type:
            return prop_type
    except Exception as e:
        import structlog
        log = structlog.get_logger()
        log.warning("llm_detect_property_type_failed", error=str(e), text=text)
    
    # Fallback para regex expandido
    text_lower = text.lower().strip()
    if text_lower in ["casa", "sobrado"]:
        return "house"
    if text_lower in ["apartamento", "apto", "ap", "flat"]:
        return "apartment"
    if text_lower in ["comercial", "loja", "sala", "sala comercial", "ponto comercial"]:
        return "commercial"
    if text_lower in ["terreno", "lote", "área"]:
        return "land"
    
    # Fallback parcial (contém palavra-chave)
    if "casa" in text_lower or "sobrado" in text_lower:
        return "house"
    if any(kw in text_lower for kw in ["apartamento", "apto", "ap", "flat"]):
        return "apartment"
    if any(kw in text_lower for kw in ["comercial", "loja", "sala"]):
        return "commercial"
    if any(kw in text_lower for kw in ["terreno", "lote"]):
        return "land"
    
    return None


def extract_price(text: str) -> Optional[float]:
    """Extrai preço via LLM (com fallback para regex)."""
    import re
    
    log.info("extract_price_START", text=text)
    
    # Tentar LLM primeiro
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        entities = result.get("entities", {})
        # Retorna preco_max se disponível, senão preco_min
        price = entities.get("preco_max") or entities.get("preco_min")
        if price is not None:
            log.info("extract_price_LLM_SUCCESS", text=text, price=price)
            return float(price)
    except Exception as e:
        # LLM falhou, usar fallback
        log.warning("llm_extract_price_failed", error=str(e), text=text)
    
    # Fallback 1: Valores por extenso (regex manual)
    text_lower = text.lower().strip()
    log.info("extract_price_FALLBACK1", text_lower=text_lower)
    
    extenso_map = {
        "cem mil": 100000, "100 mil": 100000, "100k": 100000,
        "duzentos mil": 200000, "200 mil": 200000, "200k": 200000,
        "trezentos mil": 300000, "300 mil": 300000, "300k": 300000,
        "quinhentos mil": 500000, "500 mil": 500000, "500k": 500000,
        "um milhão": 1000000, "um milhao": 1000000, "1 milhão": 1000000, "1 milhao": 1000000, "1mi": 1000000,
        "dois milhões": 2000000, "dois milhoes": 2000000, "2 milhões": 2000000, "2 milhoes": 2000000,
        "dois mil": 2000, "2 mil": 2000, "2k": 2000,
        "três mil": 3000, "tres mil": 3000, "3 mil": 3000, "3k": 3000,
    }
    for key, value in extenso_map.items():
        if key in text_lower:
            log.info("extract_price_EXTENSO_MATCH", key=key, value=value, text_lower=text_lower)
            return float(value)
    
    # Fallback 2: Regex para números
    text_clean = text.replace(".", "").replace(",", ".")
    match = re.search(r'\d+(?:\.\d+)?', text_clean)
    if match:
        try:
            price = float(match.group())
            log.info("extract_price_REGEX_MATCH", text_clean=text_clean, price=price)
            return price
        except:
            pass
    
    log.warning("extract_price_FAILED_ALL", text=text)
    return None


def extract_bedrooms(text: str) -> Optional[int]:
    """Extrai número de dormitórios via LLM (com fallback para regex)."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        dorm = result.get("entities", {}).get("dormitorios")
        return int(dorm) if dorm is not None else None
    except:
        # Fallback para regex
        import re
        text_lower = text.lower()
        if "tanto faz" in text_lower or "qualquer" in text_lower:
            return None
        match = re.search(r'(\d+)\s*(?:quarto|dorm|quartos|dormitório)', text_lower)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        # Tentar extrair número isolado
        match = re.search(r'\b(\d+)\b', text)
        if match:
            try:
                num = int(match.group(1))
                if 0 <= num <= 10:
                    return num
            except:
                pass
        return None


def is_greeting(text: str) -> bool:
    """Detecta saudação."""
    text_lower = text.lower().strip()
    greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "alo", "alô"]
    return any(g in text_lower for g in greetings)


def is_skip_neighborhood(text: str) -> bool:
    """Detecta se usuário quer pular bairro."""
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["não", "nao", "tanto faz", "qualquer", "skip"])


def detect_interest(text: str) -> bool:
    """Detecta interesse no imóvel apresentado."""
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["sim", "gostei", "quero", "interessado", "me interessa"])


def detect_next_property(text: str) -> bool:
    """Detecta pedido para próximo imóvel via LLM."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        if result.get("intent") == "proximo_imovel":
            return True
    except:
        pass
    # Fallback para regex expandido
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["próximo", "proximo", "outro", "next", "passa", "outras opções", "mais", "outro imovel"])


def detect_schedule_intent(text: str) -> bool:
    """Detecta intenção de agendar visita."""
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["agendar", "visita", "visitar", "conhecer", "ver"])


def detect_refine_search(text: str) -> bool:
    """Detecta intenção de ajustar/refazer critérios de busca via LLM."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        if result.get("intent") == "ajustar_criterios":
            return True
    except:
        pass
    # Fallback para regex
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["ajustar", "mudar", "refazer", "nova busca", "outros critérios", "vamos ajustar", "quero mudar"])


def extract_email(text: str) -> Optional[str]:
    """Extrai e-mail via regex."""
    import re
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def resolve_property_id_by_code_or_url(db, text: str) -> Optional[int]:
    """Resolve ID de imóvel por código de referência ou URL (mantido do original)."""
    from app.domain.realestate.models import Property
    from sqlalchemy import select
    
    text_clean = text.strip().upper()
    # Tentar por ref_code
    stmt = select(Property.id).where(Property.ref_code == text_clean, Property.is_active == True)
    result = db.execute(stmt).scalar()
    if result:
        return result
    
    # Tentar extrair código de URL (ex: /imovel/A1234)
    import re
    match = re.search(r'/imovel/([A-Z0-9]+)', text, re.IGNORECASE)
    if match:
        code = match.group(1).upper()
        stmt = select(Property.id).where(Property.ref_code == code, Property.is_active == True)
        result = db.execute(stmt).scalar()
        if result:
            return result
    
    return None

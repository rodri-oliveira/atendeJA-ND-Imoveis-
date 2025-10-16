"""
Funções de detecção de intenção usando LLM (substituição de detection_utils.py).
Mantém a mesma interface para compatibilidade com conversation_handlers.py.
"""
from typing import Optional
import asyncio
from app.services.llm_service import get_llm_service


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
        return result.get("entities", {}).get("tipo")
    except:
        # Fallback para regex
        text_lower = text.lower()
        if "casa" in text_lower:
            return "house"
        if any(kw in text_lower for kw in ["apartamento", "apto", "ap"]):
            return "apartment"
        if any(kw in text_lower for kw in ["comercial", "loja", "sala"]):
            return "commercial"
        if any(kw in text_lower for kw in ["terreno", "lote"]):
            return "land"
        return None


def extract_price(text: str) -> Optional[float]:
    """Extrai preço via LLM (com fallback para regex)."""
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        entities = result.get("entities", {})
        # Retorna preco_max se disponível, senão preco_min
        return entities.get("preco_max") or entities.get("preco_min")
    except:
        # Fallback para regex
        import re
        text_clean = text.replace(".", "").replace(",", ".")
        match = re.search(r'\d+(?:\.\d+)?', text_clean)
        if match:
            try:
                return float(match.group())
            except:
                pass
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
    """Detecta pedido para próximo imóvel."""
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["próximo", "proximo", "outro", "next", "passa"])


def detect_schedule_intent(text: str) -> bool:
    """Detecta intenção de agendar visita."""
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in ["agendar", "visita", "visitar", "conhecer", "ver"])


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

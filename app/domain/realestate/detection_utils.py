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


# ===== COMANDOS GLOBAIS =====

def detect_restart_command(text: str) -> bool:
    """Detecta comandos de reiniciar conversa."""
    text_lower = text.lower().strip()
    keywords = [
        "refazer", "recomeçar", "reiniciar", "começar de novo", "nova busca",
        "limpar", "resetar", "restart", "começar novamente", "zerar"
    ]
    return any(kw in text_lower for kw in keywords)


def detect_help_command(text: str) -> bool:
    """Detecta comandos de ajuda."""
    text_lower = text.lower().strip()
    keywords = ["ajuda", "help", "comandos", "opções", "o que posso fazer"]
    return any(kw in text_lower for kw in keywords)


def detect_back_command(text: str) -> bool:
    """Detecta comandos de voltar."""
    text_lower = text.lower().strip()
    keywords = ["voltar", "anterior", "back"]
    return any(kw in text_lower for kw in keywords)


# ===== DETECÇÃO DE INTENÇÃO =====

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
    """Detecta tipo de imóvel (house/apartment/commercial/land) priorizando regex."""
    # PRIORIDADE 1: Regex exato (mais confiável)
    text_lower = text.lower().strip()
    if text_lower in ["casa", "sobrado"]:
        return "house"
    if text_lower in ["apartamento", "apto", "ap", "flat"]:
        return "apartment"
    if text_lower in ["comercial", "loja", "sala", "sala comercial", "ponto comercial"]:
        return "commercial"
    if text_lower in ["terreno", "lote", "área"]:
        return "land"
    
    # PRIORIDADE 2: Regex parcial (contém palavra-chave)
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
    """Extrai preço priorizando regex/extenso (LLM como último recurso)."""
    import re
    
    log.info("extract_price_START", text=text)
    text_lower = text.lower().strip()
    
    # PRIORIDADE 1: Valores por extenso (mais confiável)
    extenso_map = {
        # Milhões
        "um milhão": 1000000, "um milhao": 1000000, "1 milhão": 1000000, "1 milhao": 1000000, "1mi": 1000000,
        "dois milhões": 2000000, "dois milhoes": 2000000, "2 milhões": 2000000, "2 milhoes": 2000000, "2mi": 2000000,
        "três milhões": 3000000, "tres milhoes": 3000000, "3 milhões": 3000000, "3 milhoes": 3000000, "3mi": 3000000,
        # Centenas de mil
        "cem mil": 100000, "100 mil": 100000, "100k": 100000,
        "duzentos mil": 200000, "200 mil": 200000, "200k": 200000,
        "trezentos mil": 300000, "300 mil": 300000, "300k": 300000,
        "quatrocentos mil": 400000, "400 mil": 400000, "400k": 400000,
        "quinhentos mil": 500000, "500 mil": 500000, "500k": 500000,
        "seiscentos mil": 600000, "600 mil": 600000, "600k": 600000,
        "setecentos mil": 700000, "700 mil": 700000, "700k": 700000,
        "oitocentos mil": 800000, "800 mil": 800000, "800k": 800000,
        "novecentos mil": 900000, "900 mil": 900000, "900k": 900000,
        # Dezenas de mil
        "dez mil": 10000, "10 mil": 10000, "10k": 10000,
        "vinte mil": 20000, "20 mil": 20000, "20k": 20000,
        "trinta mil": 30000, "30 mil": 30000, "30k": 30000,
        "quarenta mil": 40000, "40 mil": 40000, "40k": 40000,
        "cinquenta mil": 50000, "50 mil": 50000, "50k": 50000,
        "sessenta mil": 60000, "60 mil": 60000, "60k": 60000,
        "setenta mil": 70000, "70 mil": 70000, "70k": 70000,
        "oitenta mil": 80000, "80 mil": 80000, "80k": 80000,
        "noventa mil": 90000, "90 mil": 90000, "90k": 90000,
        # Milhares
        "dois mil": 2000, "2 mil": 2000, "2k": 2000,
        "três mil": 3000, "tres mil": 3000, "3 mil": 3000, "3k": 3000,
        "quatro mil": 4000, "4 mil": 4000, "4k": 4000,
        "cinco mil": 5000, "5 mil": 5000, "5k": 5000,
    }
    
    # Verificar matches (ordem decrescente de tamanho para evitar matches parciais)
    for key in sorted(extenso_map.keys(), key=len, reverse=True):
        if key in text_lower:
            value = extenso_map[key]
            log.info("extract_price_EXTENSO_MATCH", key=key, value=value, text_lower=text_lower)
            return float(value)
    
    # PRIORIDADE 2: Regex para números puros (sem "mil" ou "milhão")
    # Ex: "250000", "1500000"
    text_clean = text.replace(".", "").replace(",", "").replace(" ", "")
    match = re.search(r'\d{5,}', text_clean)  # Mínimo 5 dígitos (10k+)
    if match:
        try:
            price = float(match.group())
            log.info("extract_price_REGEX_MATCH", text_clean=text_clean, price=price)
            return price
        except:
            pass
    
    # PRIORIDADE 3: LLM (último recurso)
    llm = get_llm_service()
    try:
        result = asyncio.run(llm.extract_intent_and_entities(text))
        entities = result.get("entities", {})
        price = entities.get("preco_max") or entities.get("preco_min")
        if price is not None:
            log.info("extract_price_LLM_SUCCESS", text=text, price=price)
            return float(price)
    except Exception as e:
        log.warning("llm_extract_price_failed", error=str(e), text=text)
    
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

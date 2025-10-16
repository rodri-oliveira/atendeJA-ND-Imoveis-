"""
Utilitários de detecção de intenções e padrões no texto do usuário.
Responsabilidade: Parsing e extração de informações usando LLM quando disponível.
"""
import re
import json
import httpx
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.domain.realestate.models import Property
from app.core.config import settings
import structlog

log = structlog.get_logger()


def _call_llm_for_intent(text: str, context: str = "") -> Optional[Dict[str, Any]]:
    """
    Usa LLM para detectar intenção e extrair entidades.
    Fallback para regex se LLM não disponível.
    """
    if not settings.OLLAMA_BASE_URL:
        return None
    
    try:
        prompt = f"""Analise a mensagem e retorne APENAS um JSON válido:
{{"intent": "buy|rent|consent|interest|next|schedule|unknown", "entities": {{"cidade": null, "tipo": null, "preco_min": null, "preco_max": null, "quartos": null}}}}

Contexto: {context}
Mensagem: "{text}"

JSON:"""
        
        payload = {
            "model": settings.OLLAMA_DEFAULT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 150}
        }
        
        with httpx.Client(timeout=8) as client:
            r = client.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload)
            r.raise_for_status()
            response = r.json().get("response", "").strip()
            
            # Limpar markdown
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
    
    except Exception as e:
        log.debug("llm_intent_fallback", error=str(e))
        return None


def is_greeting(text: str) -> bool:
    """Detecta se o texto é apenas uma saudação."""
    t = (text or "").strip().lower()
    if not t:
        return False
    
    greet_tokens = ["ola", "olá", "oi", "bom dia", "boa tarde", "boa noite", "opa", "e ai", "eai"]
    if any(gt in t for gt in greet_tokens):
        intent_tokens = ["alug", "loca", "compr", "venda", "apto", "apart", "casa", "preço", "preco", "r$", "#", "ref"]
        return not any(tok in t for tok in intent_tokens)
    return False


def detect_consent(text: str) -> bool:
    """Detecta consentimento LGPD."""
    t = text.lower()
    return any(k in t for k in ["autorizo", "permito", "sim", "ok", "aceito", "concordo"])


def detect_purpose(text: str) -> Optional[str]:
    """Detecta finalidade (comprar/alugar) usando LLM com fallback para regex."""
    # Tentar LLM primeiro
    llm_result = _call_llm_for_intent(text, context="usuário informando se quer comprar ou alugar")
    if llm_result and llm_result.get("intent") in ["buy", "rent"]:
        return "sale" if llm_result["intent"] == "buy" else "rent"
    
    # Fallback para regex
    t = text.lower()
    if any(k in t for k in ["alugar", "aluguel", "loca", "arrendar"]):
        return "rent"
    elif any(k in t for k in ["comprar", "compra", "venda", "adquirir"]):
        return "sale"
    return None


def detect_property_type(text: str) -> Optional[str]:
    """Detecta tipo de imóvel."""
    t = text.lower()
    if "apart" in t:
        return "apartment"
    elif "casa" in t:
        return "house"
    elif any(k in t for k in ["comer", "comercial", "loja", "sala"]):
        return "commercial"
    elif any(k in t for k in ["terr", "lote"]):
        return "land"
    return None


def extract_price(text: str) -> Optional[float]:
    """Extrai valor numérico do texto."""
    price_match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(".", "").replace(",", "."))
    if price_match:
        try:
            return float(price_match.group(1))
        except:
            pass
    return None


def extract_bedrooms(text: str) -> Optional[int]:
    """Extrai número de quartos."""
    t = text.lower()
    if any(k in t for k in ["tanto faz", "qualquer", "nao sei", "não sei", "nao importa"]):
        return None
    
    bed_match = re.search(r"(\d+)", text)
    if bed_match:
        try:
            return int(bed_match.group(1))
        except:
            pass
    return None


def is_skip_neighborhood(text: str) -> bool:
    """Detecta se usuário quer pular bairro."""
    t = text.lower()
    return any(k in t for k in ["nao", "não", "nenhum", "sem", "tanto faz"])


def detect_interest(text: str) -> bool:
    """Detecta interesse em imóvel."""
    t = text.lower()
    return any(k in t for k in ["sim", "gostei", "quero", "interesse", "detalhes", "mais"])


def detect_next_property(text: str) -> bool:
    """Detecta pedido para próximo imóvel."""
    t = text.lower()
    return any(k in t for k in ["prox", "próx", "outro", "nao", "não"])


def detect_schedule_intent(text: str) -> bool:
    """Detecta intenção de agendar visita."""
    t = text.lower()
    return any(k in t for k in ["agendar", "visita", "sim", "quero", "marcar"])


def extract_email(text: str) -> Optional[str]:
    """Extrai e-mail do texto."""
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        return email_match.group(0)
    return None


def resolve_property_id_by_code_or_url(db: Session, text: str) -> Optional[int]:
    """
    Resolve ID do imóvel a partir de código ou URL.
    Suporta: #123, ref=A738, ref: A738, /imovel/123/
    """
    t = (text or "")
    
    # 1) Padrão #123 numérico
    m_num = re.search(r"#(\d+)", t)
    if m_num:
        try:
            return int(m_num.group(1))
        except:
            pass
    
    # 2) Código alfanumérico (ex.: A738)
    m_ref_url = re.search(r"ref=([A-Za-z0-9\-]+)", t, flags=re.IGNORECASE)
    m_ref_txt = re.search(r"ref\s*[:#]?\s*([A-Za-z0-9\-]+)", t, flags=re.IGNORECASE)
    code = None
    if m_ref_url:
        code = m_ref_url.group(1)
    elif m_ref_txt:
        code = m_ref_txt.group(1)
    
    if code:
        stmt = select(Property).where((Property.ref_code == code) | (Property.external_id == code))
        row = db.execute(stmt).scalars().first()
        if row:
            return int(row.id)
    
    # 3) Padrão de URL com /imovel/<id>/
    m_url_id = re.search(r"/imovel/(\d+)/", t)
    if m_url_id:
        try:
            return int(m_url_id.group(1))
        except:
            pass
    
    return None

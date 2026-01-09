"""
Funções de detecção de intenção usando LLM (substituição de detection_utils.py).
Mantém a mesma interface para compatibilidade com conversation_handlers.py.
VERSÃO: 2024-10-16 14:28 - Fallback robusto para valores por extenso
"""
from typing import Optional
from app.services.llm_service import get_llm_service
import structlog

log = structlog.get_logger()


# ===== DETECÇÃO SIM/NÃO =====

def detect_yes_no(text: str) -> Optional[str]:
    """
    Detecta sim/não usando hardcode + LLM.
    Retorna: "yes", "no" ou None
    """
    text_lower = text.lower().strip()
    
    # Palavras-chave diretas para SIM
    yes_keywords = [
        "sim", "yes", "claro", "com certeza", "certeza", "ok", "okay",
        "quero", "gostaria", "tenho", "vi um", "vi o", "já vi",
        "tenho interesse", "me interessa", "achei um",
        "correto", "está correto", "esta correto", "certo", "isso mesmo",
        "exato", "confirmo", "confirmado", "pode ser", "perfeito"
    ]
    
    # Palavras-chave diretas para NÃO
    no_keywords = [
        "não", "nao", "no", "nunca", "negativo", "nem",
        "ainda não", "ainda nao", "não tenho", "nao tenho",
        "não vi", "nao vi", "quero buscar", "me ajude a buscar",
        "incorreto", "errado", "não está", "nao esta"
    ]
    
    # 1) Hardcode (rápido e confiável)
    for keyword in yes_keywords:
        if keyword in text_lower:
            return "yes"
    for keyword in no_keywords:
        if keyword in text_lower:
            return "no"
    
    # 2) LLM como fallback
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        intent = result.get("intent")
        if intent == "responder_lgpd":  # LLM interpreta "sim" como responder_lgpd
            return "yes"
    except:
        pass
    
    return None


def extract_property_code(text: str) -> Optional[str]:
    """
    Extrai código de imóvel do texto.
    Formatos aceitos: A1234, ND12345, #1234, 1234
    """
    import re
    text_clean = text.strip().upper()
    
    # URL e padrões relacionados a links
    url_patterns = [
        r'/IMOVEL/([A-Z0-9]{2,10})',           # .../imovel/A1234
        r'IMOVEL[-_:/ ]([A-Z0-9]{2,10})',      # imovel-A1234, imovel: A1234
        r'REF[=:/-]([A-Z0-9]{2,10})',          # ref=A1234, ref:A1234, ref-A1234
    ]
    for pattern in url_patterns:
        m = re.search(pattern, text_clean)
        if m:
            return m.group(1)

    # Padrões de código (texto puro)
    patterns = [
        r'\b([A-Z]{1,3}\d{2,6})\b',                # A1234, ND12345
        r'REF[:\s]+([A-Z]{0,3}\d{2,6})',            # REF: A1234 ou REF: 1234
        r'C[ÓO]DIGO[:\s]+([A-Z]{0,3}\d{2,6})',      # CÓDIGO/CODIGO: A1234 ou 1234
        r'#?(\d{2,6})\b',                           # #1234, 1234 (somente dígitos)
    ]
    for pattern in patterns:
        m = re.search(pattern, text_clean)
        if m:
            return m.group(1)
    
    # Se for só números
    if text_clean.isdigit() and 2 <= len(text_clean) <= 6:
        return text_clean
    
    return None


# ===== COMANDOS GLOBAIS =====

def detect_restart_command(text: str) -> bool:
    """Detecta comandos de reiniciar conversa."""
    text_lower = text.lower().strip()
    keywords = [
        "refazer", "recomeçar", "reiniciar", "começar de novo", "nova busca",
        "limpar", "resetar", "restart", "começar novamente", "zerar"
    ]
    return any(kw in text_lower for kw in keywords)


def detect_decline_schedule(text: str) -> bool:
    """Detecta recusa de agendamento (hardcode + LLM)."""
    text_lower = text.lower().strip()
    
    # 1) Hardcode (rápido e confiável)
    decline_keywords = [
        "não quero agendar", "nao quero agendar",
        "depois eu vejo", "sem agenda", "mais tarde",
        "não agora", "nao agora", "agora não", "agora nao",
        "não posso", "nao posso", "prefiro não", "prefiro nao",
        "talvez depois", "vou pensar", "deixa pra depois",
        "não é o momento", "nao e o momento", "não tenho tempo",
        "nao tenho tempo", "sem pressa", "com calma",
        "outro dia", "outra hora", "depois vejo", "vou ver depois",
        "não precisa", "nao precisa", "dispenso", "passo",
        "não quero visita", "nao quero visita"
    ]
    
    if any(kw in text_lower for kw in decline_keywords):
        return True
    
    # 2) LLM como fallback para capturar recusas educadas
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        intent = result.get("intent", "")
        
        # Considerar intenções que indicam recusa ou adiamento
        if intent in ["recusar_agendamento", "adiar_visita", "nao_agendar"]:
            log.info("llm_detected_decline_schedule", text=text, intent=intent)
            return True
            
        # Verificar se há palavras de negação + contexto de agendamento
        has_negation = any(neg in text_lower for neg in ["não", "nao", "sem", "dispenso", "passo"])
        has_schedule_context = any(ctx in text_lower for ctx in ["agendar", "visita", "marcar", "agenda"])
        
        if has_negation and has_schedule_context:
            log.info("llm_detected_decline_by_context", text=text, negation=True, schedule_context=True)
            return True
            
    except Exception as e:
        log.warning("llm_decline_detection_failed", error=str(e), text=text)
    
    return False


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
    # 1) Heurística local (mais confiável e imediata)
    text_lower = text.lower().strip()
    if any(kw in text_lower for kw in ["não", "nao", "negativo", "não autorizo", "nao autorizo"]):
        return False
    if any(kw in text_lower for kw in ["sim", "autorizo", "aceito", "ok", "concordo"]):
        return True
    return False


def detect_purpose(text: str) -> Optional[str]:
    """Detecta finalidade (rent/sale) via LLM."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["alugar", "aluguel", "locação", "locar"]):
        return "rent"
    if any(kw in text_lower for kw in ["comprar", "compra", "venda", "vender"]):
        return "sale"

    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        return result.get("entities", {}).get("finalidade")
    except Exception:
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
        "mil": 1000, "um mil": 1000, "1 mil": 1000, "1k": 1000,
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
    
    # PRIORIDADE 2: Regex para números (aceita 3+ dígitos para casos como "até 2000")
    text_clean = text.replace(".", "").replace(",", " ")
    nums = re.findall(r"\d{3,}", text_clean)
    if nums:
        try:
            price = float(nums[-1])
            log.info("extract_price_REGEX_MATCH", text_clean=text_clean, price=price)
            return price
        except Exception:
            pass
    
    # PRIORIDADE 3: LLM (último recurso)
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
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
        result = llm.extract_intent_and_entities_sync(text)
        dorm = result.get("entities", {}).get("dormitorios")
        if dorm is not None:
            return int(dorm)
    except:
        # Ignorar erro e seguir para regex
        pass

    # Fallback para regex quando LLM não retorna valor
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
    """Detecta interesse no imóvel apresentado (hardcode + LLM)."""
    text_lower = text.lower().strip()
    
    # 1) Hardcode (rápido e confiável)
    interest_keywords = [
        "sim", "gostei", "quero", "interessado", "me interessa",
        "adorei", "amei", "é isso mesmo", "é isso", "perfeito pra mim", 
        "perfeito para mim", "é perfeito", "ideal", "é ideal",
        "exatamente isso", "é exatamente", "combina comigo", "combina", 
        "é o que procuro", "é o que eu procuro", "é isso que procuro",
        "legal", "bacana", "show", "top", "massa", "maneiro"
    ]
    
    if any(kw in text_lower for kw in interest_keywords):
        return True
    
    # 2) LLM como fallback para capturar expressões mais naturais
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        intent = result.get("intent", "")
        
        # Considerar intenções que indicam interesse
        if intent in ["interesse_imovel", "agendar_visita", "buscar_imovel"]:
            # Verificar se não é uma negação ou pedido de próximo
            if not any(neg in text_lower for neg in ["não", "nao", "próximo", "proximo", "outro"]):
                log.info("llm_detected_interest", text=text, intent=intent)
                return True
    except Exception as e:
        log.warning("llm_interest_detection_failed", error=str(e), text=text)
    
    return False


def detect_next_property(text: str) -> bool:
    """Detecta pedido para próximo imóvel (hardcode + LLM)."""
    text_lower = text.lower().strip()
    # 1) Hardcode
    if any(kw in text_lower for kw in ["próximo", "proximo", "outro", "next", "passa", "outras opções", "mais", "outro imovel"]):
        return True
    # 2) LLM
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        if result.get("intent") == "proximo_imovel":
            return True
    except:
        pass
    return False


def detect_schedule_intent(text: str) -> bool:
    """Detecta intenção de agendar visita (hardcode + LLM)."""
    text_lower = text.lower().strip()
    # 1) Hardcode
    if any(kw in text_lower for kw in ["agendar", "visita", "visitar", "conhecer", "ver", "marcar"]):
        return True
    # 2) LLM
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        # Considerar "buscar_imovel" com palavras de agendamento como positivo
        if "agendar" in text_lower or "marcar" in text_lower:
            return True
    except:
        pass
    return False


def detect_refine_search(text: str) -> bool:
    """Detecta intenção de ajustar/refazer critérios de busca (hardcode + LLM)."""
    text_lower = text.lower().strip()
    # 1) Hardcode
    if any(kw in text_lower for kw in ["ajustar", "mudar", "refazer", "nova busca", "outros critérios", "vamos ajustar", "quero mudar"]):
        return True
    # 2) LLM
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        if result.get("intent") == "ajustar_criterios":
            return True
    except:
        pass
    return False


def detect_no_match(text: str) -> bool:
    """Detecta insatisfação com resultados da busca (hardcode + LLM)."""
    text_lower = text.lower().strip()
    
    # 1) Hardcode (rápido e confiável)
    no_match_keywords = [
        "não encontrei imóvel", "nao encontrei imovel",
        "não encontrei", "nao encontrei",
        "não achei imóvel", "nao achei imovel", 
        "não achei", "nao achei",
        "nenhuma opção", "nenhuma opcao",
        "nenhum imóvel", "nenhum imovel",
        "não serviu", "nao serviu", "não serve", "nao serve",
        "não é o que procuro", "nao e o que procuro",
        "não é o que eu procuro", "nao e o que eu procuro",
        "não gostei", "nao gostei", "não curti", "nao curti",
        "não me agradou", "nao me agradou", "não agradou", "nao agradou",
        "não combina", "nao combina", "não é pra mim", "nao e pra mim",
        "não atende", "nao atende", "não satisfaz", "nao satisfaz",
        "fora do perfil", "não bate", "nao bate", "longe do ideal",
        "não é isso", "nao e isso", "não era isso", "nao era isso"
    ]
    
    if any(kw in text_lower for kw in no_match_keywords):
        return True
    
    # 2) LLM como fallback para capturar insatisfação mais sutil
    llm = get_llm_service()
    try:
        result = llm.extract_intent_and_entities_sync(text)
        intent = result.get("intent", "")
        
        # Considerar intenções que indicam insatisfação
        if intent in ["insatisfacao_resultados", "nao_encontrou_imovel", "rejeitar_opcoes"]:
            log.info("llm_detected_no_match", text=text, intent=intent)
            return True
            
        # Verificar padrões de negação + contexto de busca/imóvel
        has_negation = any(neg in text_lower for neg in ["não", "nao", "nenhum", "nenhuma"])
        has_property_context = any(ctx in text_lower for ctx in ["imóvel", "imovel", "casa", "apartamento", "opção", "opcao", "resultado"])
        
        if has_negation and has_property_context:
            # Verificar se não é apenas um "não" isolado (que seria detect_yes_no)
            if len(text_lower.split()) > 1:
                log.info("llm_detected_no_match_by_context", text=text, negation=True, property_context=True)
                return True
                
    except Exception as e:
        log.warning("llm_no_match_detection_failed", error=str(e), text=text)
    
    return False


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

"""
Utilitários de validação para o chatbot imobiliário.
Responsabilidade: Validar entradas do usuário e detectar respostas fora de contexto.
"""
from typing import Optional, Dict, Any, List
import re


def validate_bedrooms(value: Any) -> Optional[int]:
    """
    Valida número de quartos dentro de faixa razoável.
    
    Args:
        value: Valor a ser validado (pode ser int, str, float, etc.)
        
    Returns:
        int válido entre 0-10 ou None se inválido
    """
    if value is None:
        return None
        
    try:
        bedrooms = int(float(value))  # Converte float para int se necessário
        
        # Validação de faixa razoável
        if bedrooms < 0 or bedrooms > 10:
            return None
            
        return bedrooms
    except (ValueError, TypeError):
        return None


def validate_price(value: Any, purpose: str = "sale") -> Optional[float]:
    """
    Valida preço dentro de faixa razoável baseada na finalidade.
    
    Args:
        value: Valor a ser validado
        purpose: "sale" (venda) ou "rent" (aluguel)
        
    Returns:
        float válido ou None se inválido
    """
    if value is None:
        return None
        
    try:
        price = float(value)
        
        if purpose == "rent":
            # Aluguel: R$ 300 a R$ 50.000
            if price < 300 or price > 50000:
                return None
        else:  # sale
            # Venda: R$ 50.000 a R$ 10.000.000
            if price < 50000 or price > 10000000:
                return None
                
        return price
    except (ValueError, TypeError):
        return None


def validate_city(value: Any) -> Optional[str]:
    """
    Valida nome de cidade.
    
    Args:
        value: Nome da cidade
        
    Returns:
        str válida ou None se inválida
    """
    if not value or not isinstance(value, str):
        return None
        
    city = value.strip().title()
    
    # Rejeitar strings muito curtas ou com caracteres suspeitos
    if len(city) < 2:
        return None
        
    # Rejeitar se contém apenas números ou caracteres especiais
    if re.match(r'^[\d\W]+$', city):
        return None
        
    # Rejeitar palavras claramente fora de contexto
    invalid_words = [
        'cerveja', 'comida', 'bebida', 'salsicha', 'pizza', 'hamburguer',
        'futebol', 'jogo', 'filme', 'música', 'trabalho', 'escola',
        'sim', 'não', 'ok', 'obrigado', 'tchau', 'oi', 'olá'
    ]
    
    if city.lower() in invalid_words:
        return None
        
    return city


def validate_property_type(value: Any) -> Optional[str]:
    """
    Valida tipo de propriedade.
    
    Args:
        value: Tipo da propriedade
        
    Returns:
        str válida ou None se inválida
    """
    if not value or not isinstance(value, str):
        return None
        
    prop_type = value.lower().strip()
    
    # Tipos válidos conhecidos
    valid_types = {
        'house': ['casa', 'casas'],
        'apartment': ['apartamento', 'apartamentos', 'ap', 'apto', 'apt'],
        'commercial': ['comercial', 'comerciais', 'loja', 'escritório', 'escritorio'],
        'land': ['terreno', 'terrenos', 'lote', 'lotes']
    }
    
    for standard_type, variations in valid_types.items():
        if prop_type in variations:
            return standard_type
            
    return None


def is_response_in_context(text: str, expected_type: str) -> bool:
    """
    Verifica se a resposta está no contexto esperado.
    
    Args:
        text: Texto da resposta do usuário
        expected_type: Tipo de resposta esperada
        
    Returns:
        bool indicando se está no contexto
    """
    if not text or not isinstance(text, str):
        return False
        
    text_lower = text.lower().strip()
    
    # Palavras-chave por contexto
    context_keywords = {
        "bedrooms": [
            "quarto", "quartos", "dormitório", "dormitórios", "dormitorio", "dormitorios",
            "suíte", "suites", "suite", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
            "um", "dois", "três", "tres", "quatro", "cinco", "seis", "tanto faz", "qualquer"
        ],
        "price": [
            "mil", "reais", "real", "valor", "preço", "preco", "dinheiro", "custo",
            "100", "200", "300", "400", "500", "600", "700", "800", "900",
            "1000", "2000", "3000", "4000", "5000", "10000", "50000", "100000",
            "k", "milhão", "milhao", "bilhão", "bilhao"
        ],
        "city": [
            "cidade", "cidades", "município", "municipio", "local", "localidade",
            "são paulo", "rio", "mogi", "santos", "campinas", "sorocaba",
            "bairro", "região", "regiao", "zona", "centro"
        ],
        "type": [
            "casa", "casas", "apartamento", "apartamentos", "ap", "apto", "apt",
            "comercial", "comerciais", "terreno", "terrenos", "lote", "lotes",
            "escritório", "escritorio", "loja", "lojas", "galpão", "galpao"
        ],
        "purpose": [
            "comprar", "compra", "vender", "venda", "alugar", "aluguel", "locação", "locacao",
            "investir", "investimento", "morar", "residir", "negócio", "negocio"
        ]
    }
    
    keywords = context_keywords.get(expected_type, [])
    return any(keyword in text_lower for keyword in keywords)


def get_retry_limit_message(stage: str, retry_count: int) -> str:
    """
    Retorna mensagem educativa quando atinge limite de tentativas.
    
    Args:
        stage: Estágio atual da conversa
        retry_count: Número de tentativas já feitas
        
    Returns:
        Mensagem educativa para o usuário
    """
    stage_messages = {
        "awaiting_bedrooms": {
            "title": "🏠 Sobre quartos",
            "explanation": "Preciso saber quantos quartos você quer no imóvel.",
            "examples": "Exemplos válidos: '2', '3 quartos', 'tanto faz'",
            "fallback": "Vou considerar 'qualquer quantidade' de quartos para continuar."
        },
        "awaiting_price_min": {
            "title": "💰 Sobre preço mínimo",
            "explanation": "Preciso saber o valor mínimo que você considera.",
            "examples": "Exemplos: '200000', '200 mil', '200k'",
            "fallback": "Vou usar R$ 100.000 como valor mínimo para continuar."
        },
        "awaiting_price_max": {
            "title": "💰 Sobre preço máximo", 
            "explanation": "Preciso saber o valor máximo que você pode pagar.",
            "examples": "Exemplos: '500000', '500 mil', '500k'",
            "fallback": "Vou usar R$ 1.000.000 como valor máximo para continuar."
        },
        "awaiting_city": {
            "title": "🌍 Sobre cidade",
            "explanation": "Preciso saber em qual cidade você quer o imóvel.",
            "examples": "Exemplos: 'São Paulo', 'Mogi das Cruzes', 'Santos'",
            "fallback": "Vou buscar em 'São Paulo' para continuar."
        },
        "awaiting_type": {
            "title": "🏢 Sobre tipo de imóvel",
            "explanation": "Preciso saber que tipo de imóvel você quer.",
            "examples": "Exemplos: 'casa', 'apartamento', 'comercial', 'terreno'",
            "fallback": "Vou buscar 'qualquer tipo' para continuar."
        }
    }
    
    stage_info = stage_messages.get(stage, {
        "title": "ℹ️ Vamos continuar",
        "explanation": "Não consegui entender sua resposta.",
        "examples": "Tente ser mais específico.",
        "fallback": "Vou usar valores padrão para continuar."
    })
    
    return f"""
{stage_info['title']}

{stage_info['explanation']}

{stage_info['examples']}

Como você tentou {retry_count} vezes, {stage_info['fallback']}

Você pode ajustar isso depois! 😊
""".strip()


def get_context_validation_message(expected_type: str) -> str:
    """
    Retorna mensagem quando resposta está fora de contexto.
    
    Args:
        expected_type: Tipo de resposta esperada
        
    Returns:
        Mensagem educativa
    """
    messages = {
        "bedrooms": "🏠 Preciso saber sobre *quartos*. Quantos quartos você quer? (Ex: 2, 3, tanto faz)",
        "price": "💰 Preciso saber sobre *valor*. Qual o preço? (Ex: 200000, 200 mil, 500k)",
        "city": "🌍 Preciso saber sobre *cidade*. Em qual cidade? (Ex: São Paulo, Mogi das Cruzes)",
        "type": "🏢 Preciso saber sobre *tipo de imóvel*. Qual tipo? (casa, apartamento, comercial, terreno)",
        "purpose": "🎯 Preciso saber sobre *finalidade*. Você quer comprar ou alugar?"
    }
    
    return messages.get(expected_type, "Por favor, responda sobre o que foi perguntado.")


def apply_fallback_values(state: Dict[str, Any], stage: str) -> Dict[str, Any]:
    """
    Aplica valores padrão quando usuário não consegue responder adequadamente.
    
    Args:
        state: Estado atual da conversa
        stage: Estágio atual
        
    Returns:
        Estado atualizado com valores padrão
    """
    fallback_values = {
        "awaiting_bedrooms": {"bedrooms": None},  # Qualquer quantidade
        "awaiting_price_min": {"price_min": 100000},  # R$ 100k
        "awaiting_price_max": {"price_max": 1000000},  # R$ 1M
        "awaiting_city": {"city": "São Paulo"},
        "awaiting_type": {"type": None}  # Qualquer tipo
    }
    
    if stage in fallback_values:
        state.update(fallback_values[stage])
        
    return state


def validate_llm_entities(entities: Dict[str, Any], user_input: str, current_stage: str = None) -> Dict[str, Any]:
    """
    Valida entidades extraídas pelo LLM para evitar alucinações.
    
    Args:
        entities: Entidades extraídas pelo LLM
        user_input: Texto original do usuário
        current_stage: Estágio atual da conversa (opcional)
    
    Returns:
        Dict com entidades validadas (alucinações removidas)
    """
    import re
    import structlog
    
    log = structlog.get_logger()
    
    # Log inicial da validação
    log.info(
        "validation_start",
        user_input=user_input,
        current_stage=current_stage,
        original_entities=entities,
        input_length=len(user_input)
    )
    
    validated = {}
    user_lower = user_input.lower().strip()
    
    # 1. EXCEÇÃO: Números em contextos específicos são válidos
    # No estágio awaiting_purpose: "1" = sale, "2" = rent
    # No estágio awaiting_type: "1" = house, "2" = apartment, etc.
    if current_stage and user_lower in ['1', '2', '3', '4']:
        # Permitir que o handler específico do estágio processe os números
        # Não remover entidades do LLM nestes casos
        if current_stage in ['awaiting_purpose', 'awaiting_type', 'awaiting_bedrooms']:
            log.info(
                "validation_numeric_exception",
                user_input=user_input,
                current_stage=current_stage,
                action="allowing_numeric_input"
            )
            return entities
    
    # 2. REGRA: Inputs muito simples não devem gerar entidades complexas
    simple_inputs = ["sim", "não", "nao", "ok", "okay", "oi", "ola", "olá", "tchau", "obrigado", "valeu"]
    if user_lower in simple_inputs or (len(user_input.strip()) <= 3 and user_lower not in ['1', '2', '3', '4']):
        log.info(
            "validation_simple_input",
            user_input=user_input,
            action="removing_all_entities",
            reason="simple_input_detected"
        )
        return {key: None for key in entities.keys()}
    
    # 3. VALIDAÇÃO POR ENTIDADE
    for key, value in entities.items():
        original_value = value
        validated[key] = _validate_entity(key, value, user_lower, current_stage)
        
        # Log se a entidade foi modificada
        if original_value != validated[key]:
            log.info(
                "validation_entity_changed",
                entity_type=key,
                original_value=original_value,
                validated_value=validated[key],
                user_input=user_input,
                reason="failed_validation"
            )
    
    # Log final da validação
    log.info(
        "validation_complete",
        user_input=user_input,
        original_entities=entities,
        validated_entities=validated,
        changes_made=entities != validated
    )
    
    return validated


def _validate_entity(entity_type: str, value: Any, user_lower: str, current_stage: str = None) -> Any:
    """Valida uma entidade específica contra o input do usuário."""
    
    if value is None or value == "null" or value == "":
        return None
    
    # CONTEXTO ESPECÍFICO: Números em estágios específicos são válidos
    if current_stage and user_lower in ['1', '2', '3', '4']:
        if current_stage in ['awaiting_purpose', 'awaiting_type', 'awaiting_bedrooms']:
            # Permitir que o handler do estágio processe
            return value
    
    # FINALIDADE: deve ter palavras-chave relacionadas
    if entity_type == "finalidade":
        rent_keywords = ["alugar", "aluguel", "locação", "locacao", "locar", "rent"]
        sale_keywords = ["comprar", "compra", "venda", "vender", "sale", "adquirir"]
        
        if value == "rent" and not any(kw in user_lower for kw in rent_keywords):
            return None
        if value == "sale" and not any(kw in user_lower for kw in sale_keywords):
            return None
    
    # TIPO: deve ter palavras-chave relacionadas
    elif entity_type == "tipo":
        type_keywords = {
            "house": ["casa", "sobrado", "house"],
            "apartment": ["apartamento", "apto", "ap", "apartment", "flat"],
            "commercial": ["comercial", "loja", "sala", "commercial", "escritório", "escritorio"],
            "land": ["terreno", "lote", "land", "área", "area"]
        }
        
        if value in type_keywords:
            keywords = type_keywords[value]
            if not any(kw in user_lower for kw in keywords):
                return None
    
    # CIDADE: deve parecer um nome de cidade válido
    elif entity_type == "cidade":
        if isinstance(value, str):
            # Remover strings "null" ou muito curtas
            if value.lower() in ["null", "none", ""] or len(value) < 2:
                return None
            # Verificar se contém apenas letras, espaços e acentos
            if not re.match(r'^[a-záàâãéèêíìîóòôõúùûçñ\s]+$', value.lower()):
                return None
    
    # PREÇOS: devem ser números válidos e razoáveis
    elif entity_type in ["preco_min", "preco_max"]:
        if isinstance(value, (int, float)):
            # Preços muito baixos ou altos são suspeitos
            if value < 100 or value > 50000000:
                return None
        else:
            return None
    
    # DORMITÓRIOS: deve ser número inteiro razoável
    elif entity_type == "dormitorios":
        if isinstance(value, (int, float)):
            dormitorios = int(value)
            if dormitorios < 0 or dormitorios > 10:
                return None
            return dormitorios
        else:
            return None
    
    return value


def sanitize_llm_result(llm_result: Dict[str, Any], user_input: str, current_stage: str = None) -> Dict[str, Any]:
    """
    Sanitiza resultado completo do LLM (intent + entities).
    
    Args:
        llm_result: Resultado bruto do LLM
        user_input: Input original do usuário
        current_stage: Estágio atual da conversa
    
    Returns:
        Resultado sanitizado
    """
    import structlog
    log = structlog.get_logger()
    
    # Log inicial da sanitização
    log.info(
        "sanitize_start",
        user_input=user_input,
        current_stage=current_stage,
        raw_llm_result=llm_result
    )
    
    # Extrair dados do resultado
    intent = llm_result.get("intent", "outro")
    entities = llm_result.get("entities", {})
    
    log.info(
        "sanitize_extracted_data",
        intent=intent,
        entities=entities,
        user_input=user_input
    )
    
    # Validar entidades
    validated_entities = validate_llm_entities(entities, user_input, current_stage)
    
    # Log para debug
    if entities != validated_entities:
        log.warning(
            "llm_hallucination_detected",
            user_input=user_input,
            original_entities=entities,
            validated_entities=validated_entities,
            removed_entities=[k for k, v in entities.items() if v != validated_entities.get(k)]
        )
    else:
        log.info(
            "sanitize_no_changes",
            user_input=user_input,
            entities=entities,
            message="no_hallucinations_detected"
        )
    
    sanitized_result = {
        "intent": intent,
        "entities": validated_entities
    }
    
    # Log final da sanitização
    log.info(
        "sanitize_complete",
        user_input=user_input,
        original_result=llm_result,
        sanitized_result=sanitized_result,
        changes_made=llm_result != sanitized_result
    )
    
    return sanitized_result


def get_entity_keywords(entity_type: str) -> List[str]:
    """Retorna palavras-chave esperadas para um tipo de entidade."""
    keywords_map = {
        "finalidade": ["alugar", "aluguel", "locação", "comprar", "compra", "venda", "vender"],
        "tipo": ["casa", "apartamento", "apto", "comercial", "terreno", "sobrado", "loja"],
        "cidade": [],  # Cidades são validadas por padrão, não por keywords
        "preco_min": ["mínimo", "minimo", "pelo menos", "acima de", "a partir"],
        "preco_max": ["máximo", "maximo", "até", "no máximo", "limite"],
        "dormitorios": ["quarto", "quartos", "dormitório", "dormitorios", "suíte", "suite"]
    }
    return keywords_map.get(entity_type, [])
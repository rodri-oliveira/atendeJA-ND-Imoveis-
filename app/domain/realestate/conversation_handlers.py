"""
Handlers de estágios da conversa do chatbot imobiliário.
Responsabilidade: Lógica de transição entre estágios e processamento de entrada.
"""
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.domain.realestate import detection_utils_llm as detect
from app.domain.realestate import message_formatters as fmt
from app.domain.realestate.models import Property, PropertyImage
from app.services.lead_service import LeadService
from sqlalchemy import select


class ConversationHandler:
    """Gerenciador de estágios da conversa."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def handle_start(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """
        Estágio inicial: detecta lead direcionado ou inicia saudação.
        
        Returns:
            (mensagem, novo_state, continuar_loop)
        """
        # Detectar lead direcionado
        imovel_id = detect.resolve_property_id_by_code_or_url(self.db, text)
        if imovel_id:
            state["directed_property_id"] = imovel_id
            state["stage"] = "show_directed_property"
            return ("", state, True)  # Continuar loop
        
        # Lead frio - saudação
        if detect.is_greeting(text):
            msg = fmt.format_welcome_message()
            state["stage"] = "awaiting_lgpd_consent"
            return (msg, state, False)
        else:
            # Não é saudação, avançar para LGPD
            state["stage"] = "awaiting_lgpd_consent"
            return ("", state, True)
    
    def handle_lgpd_consent(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de consentimento LGPD."""
        if detect.detect_consent(text):
            state["lgpd_consent"] = True
            state["stage"] = "awaiting_purpose"
            msg = "Legal! Para começarmos, me diga: você procura um imóvel para *comprar* ou para *alugar*?"
            return (msg, state, False)
        else:
            msg = "Por favor, responda com 'sim' ou 'autorizo' para que possamos continuar com segurança. 🔒"
            return (msg, state, False)
    
    def handle_purpose(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de finalidade (comprar/alugar)."""
        import structlog
        log = structlog.get_logger()
        
        purpose = detect.detect_purpose(text)
        log.info("detect_purpose_result", text=text, detected_purpose=purpose)
        
        if purpose:
            state["purpose"] = purpose
            state["stage"] = "awaiting_type"
            msg = "Perfeito! Agora me diga, você prefere *casa*, *apartamento* ou *comercial*?"
            log.info("purpose_detected", purpose=purpose, next_stage="awaiting_type")
            return (msg, state, False)
        else:
            msg = "Não entendi. Você gostaria de *comprar* ou *alugar* um imóvel?"
            log.warning("purpose_not_detected", text=text)
            return (msg, state, False)
    
    def handle_city(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de cidade."""
        cidade = text.strip().title()
        state["city"] = cidade
        state["stage"] = "awaiting_neighborhood"
        msg = f"Ótimo! Você tem preferência por algum *bairro* em {cidade}? (ou 'não')"
        return (msg, state, False)
    
    def handle_type(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de tipo de imóvel."""
        prop_type = detect.detect_property_type(text)
        
        if prop_type:
            state["type"] = prop_type
            state["stage"] = "awaiting_price_min"
            purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
            msg = f"Entendido! Qual o valor *mínimo* que você considera para {purpose_txt}? (Ex: 200000 ou 2000)"
            return (msg, state, False)
        else:
            msg = "Não entendi o tipo. Por favor, escolha: *casa*, *apartamento*, *comercial* ou *terreno*."
            return (msg, state, False)
    
    def handle_price_min(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de preço mínimo."""
        price_min = detect.extract_price(text)
        
        if price_min is not None:
            state["price_min"] = price_min
            state["stage"] = "awaiting_price_max"
            purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
            msg = f"Perfeito! E qual o valor *máximo* para {purpose_txt}?"
            return (msg, state, False)
        else:
            msg = "Não consegui identificar o valor. Por favor, informe o valor mínimo em números (ex: 200000)."
            return (msg, state, False)
    
    def handle_price_max(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de preço máximo."""
        price_max = detect.extract_price(text)
        
        if price_max is not None:
            state["price_max"] = price_max
            state["stage"] = "awaiting_bedrooms"
            msg = "Ótimo! Quantos quartos você precisa? (Ex: 2, 3 ou 'tanto faz')"
            return (msg, state, False)
        else:
            msg = "Não consegui identificar o valor. Por favor, informe o valor máximo em números (ex: 500000)."
            return (msg, state, False)
    
    def handle_bedrooms(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de quartos."""
        bedrooms = detect.extract_bedrooms(text)
        
        state["bedrooms"] = bedrooms
        state["stage"] = "awaiting_city"
        msg = "Perfeito! Em qual cidade você está procurando?"
        return (msg, state, False)
    
    def handle_neighborhood(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de bairro."""
        if detect.is_skip_neighborhood(text):
            state["neighborhood"] = None
        else:
            state["neighborhood"] = text.strip().title()
        
        state["stage"] = "searching"
        return ("", state, True)  # Continuar para busca
    
    def handle_searching(self, sender_id: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de busca de imóveis."""
        from app.domain.realestate.models import PropertyType, PropertyPurpose
        
        # Montar query
        stmt = select(Property).where(Property.is_active == True)
        
        if state.get("purpose"):
            stmt = stmt.where(Property.purpose == PropertyPurpose(state["purpose"]))
        if state.get("type"):
            stmt = stmt.where(Property.type == PropertyType(state["type"]))
        if state.get("city"):
            stmt = stmt.where(Property.address_city.ilike(f"%{state['city']}%"))
        if state.get("neighborhood"):
            stmt = stmt.where(Property.address_neighborhood.ilike(f"%{state['neighborhood']}%"))
        if state.get("price_min") is not None:
            stmt = stmt.where(Property.price >= float(state["price_min"]))
        if state.get("price_max") is not None:
            stmt = stmt.where(Property.price <= float(state["price_max"]))
        if state.get("bedrooms") is not None:
            stmt = stmt.where(Property.bedrooms >= int(state["bedrooms"]))
        
        stmt = stmt.limit(20)
        results = self.db.execute(stmt).scalars().all()
        
        if not results:
            # Sem resultados - salvar lead
            LeadService.create_unqualified_lead(
                self.db,
                sender_id,
                state,
                state.get("lgpd_consent", False)
            )
            msg = fmt.format_no_results_message(state.get("city", "sua cidade"))
            return (msg, {}, False)  # Limpar state
        
        # Salvar IDs dos resultados
        state["search_results"] = [r.id for r in results]
        state["current_property_index"] = 0
        state["stage"] = "showing_property"
        return ("", state, True)  # Continuar para mostrar primeiro imóvel
    
    def handle_showing_property(self, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de apresentação de imóvel."""
        results = state.get("search_results", [])
        idx = state.get("current_property_index", 0)
        
        if idx >= len(results):
            msg = fmt.format_end_of_results_message()
            return (msg, {}, False)  # Limpar state
        
        # Buscar detalhes do imóvel
        prop_id = results[idx]
        prop = self.db.get(Property, prop_id)
        
        if not prop:
            # Imóvel não encontrado, pular para próximo
            state["current_property_index"] = idx + 1
            return ("", state, True)
        
        # Formatar card do imóvel
        prop_details = {
            "id": prop.id,
            "ref_code": prop.ref_code,
            "external_id": prop.external_id,
            "titulo": prop.title,
            "tipo": prop.type.value,
            "preco": prop.price,
            "cidade": prop.address_city,
            "estado": prop.address_state,
            "bairro": prop.address_neighborhood,
            "dormitorios": prop.bedrooms,
        }
        
        msg = fmt.format_property_card(prop_details, state.get("purpose", "rent"))
        state["stage"] = "awaiting_property_feedback"
        return (msg, state, False)
    
    def handle_property_feedback(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de feedback do imóvel apresentado."""
        if detect.detect_interest(text):
            # Cliente interessado - mostrar detalhes
            results = state.get("search_results", [])
            idx = state.get("current_property_index", 0)
            prop_id = results[idx]
            prop = self.db.get(Property, prop_id)
            
            if not prop:
                msg = "Desculpe, houve um erro. Vamos para o próximo imóvel."
                state["current_property_index"] = idx + 1
                state["stage"] = "showing_property"
                return (msg, state, True)
            
            prop_details = {
                "descricao": prop.description,
                "dormitorios": prop.bedrooms,
                "banheiros": prop.bathrooms,
                "vagas": prop.parking_spots,
                "area_total": prop.area_total,
            }
            
            msg = fmt.format_property_details(prop_details)
            state["interested_property_id"] = prop_id
            state["stage"] = "awaiting_visit_decision"
            return (msg, state, False)
        
        elif detect.detect_next_property(text):
            # Próximo imóvel
            state["current_property_index"] = state.get("current_property_index", 0) + 1
            state["stage"] = "showing_property"
            return ("", state, True)
        else:
            msg = "Digite *'sim'* se gostou ou *'próximo'* para ver outra opção."
            return (msg, state, False)
    
    def handle_visit_decision(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de decisão de agendamento."""
        if detect.detect_schedule_intent(text):
            state["stage"] = "collecting_name"
            msg = "Perfeito! Para agendar a visita, preciso de alguns dados. Qual é o seu *nome completo*?"
            return (msg, state, False)
        elif detect.detect_next_property(text):
            # Próximo imóvel
            state["current_property_index"] = state.get("current_property_index", 0) + 1
            state["stage"] = "showing_property"
            return ("", state, True)
        else:
            msg = "Digite *'agendar'* para marcar uma visita ou *'próximo'* para ver outras opções."
            return (msg, state, False)
    
    def handle_collecting_name(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de coleta de nome."""
        name = text.strip().title()
        if len(name) < 3:
            msg = "Por favor, informe seu nome completo."
            return (msg, state, False)
        
        state["lead_name"] = name
        state["stage"] = "collecting_email"
        first_name = name.split()[0]
        msg = f"Obrigado, {first_name}! Agora preciso do seu *e-mail*."
        return (msg, state, False)
    
    def handle_collecting_email(
        self,
        text: str,
        sender_id: str,
        state: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de coleta de e-mail e finalização."""
        email = detect.extract_email(text)
        
        if not email:
            msg = "Por favor, informe um e-mail válido (ex: seunome@email.com)."
            return (msg, state, False)
        
        # Criar lead qualificado
        LeadService.create_qualified_lead(
            self.db,
            sender_id,
            state.get("lead_name"),
            email,
            state,
            state.get("interested_property_id")
        )
        
        msg = fmt.format_schedule_confirmation(state.get("lead_name"))
        return (msg, {}, False)  # Limpar state

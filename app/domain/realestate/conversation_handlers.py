"""
Handlers de estágios da conversa do chatbot imobiliário.
Responsabilidade: Lógica de transição entre estágios e processamento de entrada.
"""
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.domain.realestate import detection_utils as detect
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
        
        # Priorizar LLM
        ent = (state.get("llm_entities") or {})
        purpose = ent.get("finalidade") or detect.detect_purpose(text)
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
        import structlog
        log = structlog.get_logger()
        
        ent = (state.get("llm_entities") or {})
        cidade = (ent.get("cidade") or text).strip().title()
        state["city"] = cidade
        
        # Log para debug: verificar se type está preservado
        log.info("handle_city_state", 
                 city=cidade,
                 type=state.get("type"),
                 purpose=state.get("purpose"),
                 price_max=state.get("price_max"))
            
        # Se já tem tipo e preço (refinamento), buscar direto após bairro
        if state.get("type") and state.get("price_max"):
            state["stage"] = "awaiting_neighborhood"
        else:
            state["stage"] = "awaiting_neighborhood"
        msg = f"Ótimo! Você tem preferência por algum *bairro* em {cidade}? (ou 'não')"
        return (msg, state, False)
    
    def handle_type(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de tipo de imóvel."""
        ent = (state.get("llm_entities") or {})
        prop_type = ent.get("tipo") or detect.detect_property_type(text)
        
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
        import structlog
        log = structlog.get_logger()
        
        # PRIORIDADE: extract_price (regex/extenso) sobre LLM
        price_min = detect.extract_price(text)
        if price_min is None:
            ent = (state.get("llm_entities") or {})
            price_min = ent.get("preco_min")
        
        log.info("handle_price_min", input_text=text, extracted_price=price_min)
        
        if price_min is not None:
            state["price_min"] = price_min
            
            # Se já tem cidade (refinamento), buscar direto SEM mensagem
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)  # Busca silenciosa
            else:
                # Primeira vez, continuar fluxo normal
                state["stage"] = "awaiting_price_max"
                purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
                msg = f"Perfeito! E qual o valor *máximo* para {purpose_txt}?"
                return (msg, state, False)
        else:
            msg = "Não consegui identificar o valor. Por favor, informe o valor mínimo em números (ex: 200000)."
            return (msg, state, False)
    
    def handle_price_max(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de preço máximo."""
        # PRIORIDADE: extract_price (regex/extenso) sobre LLM
        price_max = detect.extract_price(text)
        if price_max is None:
            ent = (state.get("llm_entities") or {})
            price_max = ent.get("preco_max")
        
        if price_max is not None:
            state["price_max"] = price_max
            
            # Se já tem cidade (refinamento), buscar direto SEM mensagem
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)  # Busca silenciosa
            else:
                # Primeira vez, continuar fluxo normal
                state["stage"] = "awaiting_bedrooms"
                msg = "Ótimo! Quantos quartos você precisa? (Ex: 2, 3 ou 'tanto faz')"
                return (msg, state, False)
        else:
            msg = "Não consegui identificar o valor. Por favor, informe o valor máximo em números (ex: 500000)."
            return (msg, state, False)
    
    def handle_bedrooms(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de quartos."""
        ent = (state.get("llm_entities") or {})
        bedrooms = ent.get("dormitorios")
        if bedrooms is None:
            bedrooms = detect.extract_bedrooms(text)
        
        state["bedrooms"] = bedrooms
        
        # Se já tem cidade (refinamento), buscar direto SEM mensagem
        if state.get("city"):
            state["stage"] = "searching"
            return ("", state, True)  # Busca silenciosa
        
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
        import structlog
        log = structlog.get_logger()
        from app.domain.realestate.models import PropertyType, PropertyPurpose
        
        # Log dos critérios de busca
        log.info("searching_criteria", 
                 purpose=state.get("purpose"),
                 type=state.get("type"),
                 city=state.get("city"),
                 price_min=state.get("price_min"),
                 price_max=state.get("price_max"),
                 bedrooms=state.get("bedrooms"))
        
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
            # IMPORTANTE: Manter TODOS os critérios para permitir refinamento pontual
            state["stage"] = "awaiting_refinement"
            return (msg, state, False)
        
        # Salvar IDs dos resultados
        state["search_results"] = [r.id for r in results]
        state["current_property_index"] = 0
        state["stage"] = "showing_property"
        return ("", state, True)  # Continuar para mostrar primeiro imóvel
    
    def handle_showing_property(self, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de apresentação de imóveis."""
        results = state.get("search_results", [])
        idx = state.get("current_property_index", 0)
        
        # Se não há mais imóveis
        if idx >= len(results):
            msg = fmt.format_no_more_properties()
            state["stage"] = "awaiting_refinement"  # Aguardar decisão de ajustar critérios
            return (msg, state, False)
        
        # Buscar próximo imóvel
        prop_id = results[idx]
        prop = self.db.get(Property, prop_id)
        
        if not prop:
            # Imóvel não encontrado, pular para próximo
            state["current_property_index"] = idx + 1
            return ("", state, True)
        
        # Formatar card do imóvel com contador
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
        
        # Adicionar contador: "Imóvel 1 de 3"
        total = len(results)
        current = idx + 1
        counter = f"\n\n📊 Imóvel {current} de {total}" if total > 1 else ""
        
        msg = fmt.format_property_card(prop_details, state.get("purpose", "rent")) + counter
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
            # Verificar se quer ajustar critérios
            llm_intent = state.get("llm_intent", "")
            if llm_intent == "ajustar_criterios" or any(kw in text.lower() for kw in ["ajustar", "refinar", "mudar critério", "mudar criterio"]):
                # Mostrar critérios atuais e pedir especificação
                current_criteria = []
                if state.get("purpose"):
                    current_criteria.append(f"• Finalidade: {self._translate_purpose(state['purpose'])}")
                if state.get("type"):
                    current_criteria.append(f"• Tipo: {self._translate_type(state['type'])}")
                if state.get("price_min"):
                    current_criteria.append(f"• Valor mínimo: R$ {state['price_min']:,.2f}")
                if state.get("price_max"):
                    current_criteria.append(f"• Valor máximo: R$ {state['price_max']:,.2f}")
                if state.get("bedrooms"):
                    current_criteria.append(f"• Quartos: {state['bedrooms']}")
                if state.get("city"):
                    current_criteria.append(f"• Cidade: {state['city']}")
                
                criteria_text = "\n".join(current_criteria) if current_criteria else "Nenhum critério definido ainda."
                
                msg = (
                    f"📋 *Seus critérios atuais:*\n{criteria_text}\n\n"
                    "Seja mais específico, por favor. Exemplos:\n"
                    "• \"ajustar o valor máximo\"\n"
                    "• \"mudar para apartamento\"\n"
                    "• \"buscar em outra cidade\"\n"
                    "• \"quero 3 quartos\"\n"
                    "• \"recomeçar do zero\""
                )
                state["stage"] = "awaiting_refinement"
                return (msg, state, False)
            
            msg = "Gostou deste imóvel? Digite *'sim'* para mais detalhes, *'próximo'* para ver outra opção ou *'ajustar critérios'* para refinar a busca."
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
            # Verificar se quer ajustar critérios
            llm_intent = state.get("llm_intent", "")
            if llm_intent == "ajustar_criterios" or any(kw in text.lower() for kw in ["ajustar", "refinar", "mudar critério", "mudar criterio"]):
                # Mostrar critérios atuais e pedir especificação
                current_criteria = []
                if state.get("purpose"):
                    current_criteria.append(f"• Finalidade: {self._translate_purpose(state['purpose'])}")
                if state.get("type"):
                    current_criteria.append(f"• Tipo: {self._translate_type(state['type'])}")
                if state.get("price_min"):
                    current_criteria.append(f"• Valor mínimo: R$ {state['price_min']:,.2f}")
                if state.get("price_max"):
                    current_criteria.append(f"• Valor máximo: R$ {state['price_max']:,.2f}")
                if state.get("bedrooms"):
                    current_criteria.append(f"• Quartos: {state['bedrooms']}")
                if state.get("city"):
                    current_criteria.append(f"• Cidade: {state['city']}")
                
                criteria_text = "\n".join(current_criteria) if current_criteria else "Nenhum critério definido ainda."
                
                msg = (
                    f"📋 *Seus critérios atuais:*\n{criteria_text}\n\n"
                    "Seja mais específico, por favor. Exemplos:\n"
                    "• \"ajustar o valor máximo\"\n"
                    "• \"mudar para apartamento\"\n"
                    "• \"buscar em outra cidade\"\n"
                    "• \"quero 3 quartos\"\n"
                    "• \"recomeçar do zero\""
                )
                state["stage"] = "awaiting_refinement"
                return (msg, state, False)
            
            msg = "Digite *'agendar'* para marcar uma visita, *'próximo'* para ver outras opções ou *'ajustar critérios'* para refinar a busca."
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
    
    def handle_refinement(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        """Estágio de decisão após ver todos os imóveis ou não gostar."""
        import structlog
        log = structlog.get_logger()
        
        # ===== PASSO 1: LLM INTERPRETA A INTENÇÃO =====
        llm_entities = state.get("llm_entities", {})
        text_lower = text.lower()
        
        log.info("refinement_llm_entities", entities=llm_entities, text=text)
        
        # ===== REFINAMENTO INTELIGENTE =====
        # Detectar qual campo específico o usuário quer mudar
        # ORDEM: 1) LLM entities, 2) Regex específico, 3) Fallback educado
        
        # 0. Mudança de QUARTOS (se já especificou número)
        bedrooms_from_llm = llm_entities.get("dormitorios")
        if bedrooms_from_llm and any(kw in text_lower for kw in ["quarto", "dormitório", "dormitorio"]):
            # Usuário já disse "quero 3 quartos" - aplicar direto
            state["bedrooms"] = bedrooms_from_llm
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)  # Busca silenciosa
            else:
                msg = "Perfeito! Em qual cidade você está procurando?"
                state["stage"] = "awaiting_city"
                return (msg, state, False)
        
        # 1. Mudança de PREÇO MÁXIMO (verificar ANTES de tipo)
        if any(kw in text_lower for kw in ["valor máximo", "preço máximo", "valor maximo", "preco maximo", "aumentar valor", "mais caro"]):
            msg = "Entendido! Qual o *novo valor máximo* que você considera?"
            state["stage"] = "awaiting_price_max"
            return (msg, state, False)
        
        # 2. Mudança de PREÇO MÍNIMO
        if any(kw in text_lower for kw in ["valor mínimo", "preço mínimo", "valor minimo", "preco minimo", "diminuir valor", "mais barato"]):
            msg = "Entendido! Qual o *novo valor mínimo* que você considera?"
            state["stage"] = "awaiting_price_min"
            return (msg, state, False)
        
        # 3. Mudança de TIPO (casa/apartamento/comercial)
        # Só aceita se usuário REALMENTE mencionou o tipo (evitar alucinações do LLM)
        new_type = llm_entities.get("tipo")
        invalid_types = ["ajustar", "ajustar_criterios", "ajustar_valor", "null"]
        
        # Mapear tipos para palavras-chave que devem estar no texto
        type_keywords = {
            "house": ["casa"],
            "apartment": ["apartamento", "ap"],
            "commercial": ["comercial", "loja", "sala"],
            "land": ["terreno", "lote"]
        }
        
        # Só aceita se: tipo válido + não é mudança de preço + usuário mencionou palavra-chave
        if new_type and new_type not in invalid_types and not any(kw in text_lower for kw in ["valor", "preço", "preco"]):
            # Verificar se usuário realmente mencionou o tipo
            keywords = type_keywords.get(new_type, [])
            if any(kw in text_lower for kw in keywords):
                state["type"] = new_type
                state["stage"] = "searching"
                return ("", state, True)  # Busca silenciosa
        
        # Fallback para tipo por palavra-chave (se não for preço)
        if any(kw in text_lower for kw in ["apartamento", "casa", "comercial", "terreno"]) and not any(kw in text_lower for kw in ["valor", "preço", "preco"]):
            # Detectar qual tipo
            if "apartamento" in text_lower or "ap" in text_lower.split():
                new_type = "apartment"
            elif "casa" in text_lower:
                new_type = "house"
            elif "comercial" in text_lower:
                new_type = "commercial"
            elif "terreno" in text_lower:
                new_type = "land"
            
            if new_type:
                state["type"] = new_type
                state["stage"] = "searching"
                return ("", state, True)  # Busca silenciosa
        
        # 4. Mudança de CIDADE
        if any(kw in text_lower for kw in ["cidade", "outra cidade", "mudar cidade", "local", "região"]):
            msg = "Entendido! Em qual *cidade* você gostaria de buscar?"
            state["stage"] = "awaiting_city"
            return (msg, state, False)
        
        # 5. Mudança de BAIRRO
        if any(kw in text_lower for kw in ["bairro", "outro bairro", "mudar bairro"]):
            msg = "Entendido! Qual *bairro* você prefere?"
            state["stage"] = "awaiting_neighborhood"
            return (msg, state, False)
        
        # 6. Mudança de QUARTOS
        if any(kw in text_lower for kw in ["quartos", "dormitórios", "dormitorios", "quarto"]):
            msg = "Entendido! Quantos *quartos* você precisa?"
            state["stage"] = "awaiting_bedrooms"
            return (msg, state, False)
        
        # 7. RESETAR TUDO (apenas se explícito)
        if any(kw in text_lower for kw in ["tudo", "do zero", "recomeçar", "resetar", "começar de novo"]):
            msg = "Perfeito! Vamos recomeçar. Você quer *comprar* ou *alugar*?"
            new_state = {
                "stage": "awaiting_purpose",
                "lgpd_consent": state.get("lgpd_consent", True)
            }
            return (msg, new_state, False)
        
        # 8. Fallback educado: não entendeu, pede para ser mais específico
        current_criteria = []
        if state.get("purpose"):
            current_criteria.append(f"• Finalidade: {self._translate_purpose(state['purpose'])}")
        if state.get("type"):
            current_criteria.append(f"• Tipo: {self._translate_type(state['type'])}")
        if state.get("price_min"):
            current_criteria.append(f"• Valor mínimo: R$ {state['price_min']:,.2f}")
        if state.get("price_max"):
            current_criteria.append(f"• Valor máximo: R$ {state['price_max']:,.2f}")
        if state.get("bedrooms_min"):
            current_criteria.append(f"• Quartos: {state['bedrooms_min']}+")
        if state.get("city"):
            current_criteria.append(f"• Cidade: {state['city']}")
        
        criteria_text = "\n".join(current_criteria) if current_criteria else "Nenhum critério definido ainda."
        
        msg = (
            f"Desculpe, não entendi exatamente o que você quer ajustar. 😅\n\n"
            f"📋 *Seus critérios atuais:*\n{criteria_text}\n\n"
            "Seja mais específico, por favor. Exemplos:\n"
            "• \"ajustar o valor máximo\"\n"
            "• \"mudar para apartamento\"\n"
            "• \"buscar em outra cidade\"\n"
            "• \"quero 3 quartos\"\n"
            "• \"recomeçar do zero\""
        )
        return (msg, state, False)
    
    def _translate_purpose(self, purpose: str) -> str:
        """Traduz finalidade para português."""
        return "Compra" if purpose == "sale" else "Aluguel"
    
    def _translate_type(self, prop_type: str) -> str:
        """Traduz tipo de imóvel para português."""
        translations = {
            "house": "casa",
            "apartment": "apartamento",
            "commercial": "comercial",
            "land": "terreno"
        }
        return translations.get(prop_type, prop_type)

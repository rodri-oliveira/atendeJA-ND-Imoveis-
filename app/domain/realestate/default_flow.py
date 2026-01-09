# -*- coding: utf-8 -*-
"""Fonte única da verdade para o mapeamento de stages legados para handlers."""

# Mapeia o ID do stage (nó do flow) para o nome do handler (sem o prefixo 'handle_').
LEGACY_STAGE_TO_HANDLER_MAP = {
    "start": "start",
    "show_directed_property": "show_directed_property",
    "awaiting_lgpd_consent": "lgpd_consent",
    "awaiting_name": "name",
    "awaiting_has_property_in_mind": "has_property_in_mind",
    "awaiting_property_code": "property_code",
    "awaiting_property_questions": "property_questions",
    "awaiting_search_choice": "search_choice",
    "awaiting_schedule_visit_question": "schedule_visit_question",
    "awaiting_phone_confirmation": "phone_confirmation",
    "awaiting_phone_input": "phone_input",
    "awaiting_visit_date": "visit_date",
    "awaiting_visit_time": "visit_time",
    "awaiting_purpose": "purpose",
    "awaiting_city": "city",
    "awaiting_type": "type",
    "awaiting_price_min": "price_min",
    "awaiting_price_max": "price_max",
    "awaiting_bedrooms": "bedrooms",
    "awaiting_neighborhood": "neighborhood",
    "searching": "searching",
    "showing_property": "showing_property",
    "awaiting_property_feedback": "property_feedback",
    "awaiting_visit_decision": "visit_decision",
    "awaiting_refinement": "refinement",
}


def get_default_flow_nodes():
    """Gera a lista de nós para o flow default a partir do mapa legado."""
    nodes = []
    for stage, handler in LEGACY_STAGE_TO_HANDLER_MAP.items():
        if stage == "awaiting_has_property_in_mind":
            # Primeiro nó 100% data-driven (Phase 1): decisão sim/não para fluxo direcionado vs qualificação.
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.prompt_and_branch",
                    "prompt": "Você já viu algum imóvel específico que te interessou?\n\n1️⃣ *Sim* - Já tenho um código/referência\n2️⃣ *Não* - Quero que você me ajude a buscar\n\nDigite 1 ou 2, ou escreva 'sim' ou 'não'.",
                    "transitions": [
                        {"to": "awaiting_property_code", "when": {"yes_no": "yes"}},
                        {"to": "awaiting_purpose", "when": {"yes_no": "no"}},
                        {"to": "awaiting_property_code", "when": {"equals_any": ["1", "1️⃣", "um", "primeiro"]}},
                        {"to": "awaiting_purpose", "when": {"equals_any": ["2", "2️⃣", "dois", "segundo"]}},
                        {
                            "to": "awaiting_purpose",
                            "when": {"contains_any": ["ajuda", "ajudar", "buscar", "procurar", "encontrar", "não sei", "nao sei"]},
                        },
                        {"to": "awaiting_purpose", "when": {"default": True}},
                    ],
                }
            )
            continue

        if stage == "awaiting_search_choice":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.prompt_and_branch",
                    "prompt": "Entendi que você quer ver outras opções! 🏠\n\nVocê prefere:\n1️⃣ Informar outro código de imóvel específico\n2️⃣ Fazer uma busca personalizada (por tipo, cidade, preço)\n\nDigite *1* para código ou *2* para busca personalizada.",
                    "transitions": [
                        {
                            "to": "awaiting_property_code",
                            "when": {"equals_any": ["1", "código", "codigo"]},
                            "effects": {
                                "message": "Por favor, informe o código do imóvel que deseja ver (ex: A1234, ND12345).",
                                "continue_loop": False,
                            },
                        },
                        {
                            "to": "awaiting_purpose",
                            "when": {"equals_any": ["2", "busca", "personalizada", "buscar"]},
                            "effects": {
                                "reset_state_keep": ["sender_id", "tenant_id", "user_name", "lgpd_consent"],
                                "message": "Perfeito! Vamos fazer uma busca personalizada.\n\nVocê procura imóvel para *comprar* ou *alugar*?",
                                "continue_loop": False,
                            },
                        },
                        {
                            "to": "awaiting_search_choice",
                            "when": {"default": True},
                            "effects": {
                                "message": "Por favor, digite:\n*1* para informar um código de imóvel\n*2* para fazer uma busca personalizada",
                                "continue_loop": False,
                            },
                        },
                    ],
                }
            )
            continue

        if stage == "awaiting_schedule_visit_question":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.prompt_and_branch",
                    "prompt": "Gostaria de agendar uma visita para conhecer o imóvel pessoalmente? 📅",
                    "transitions": [
                        {
                            "to": "awaiting_phone_confirmation",
                            "when": {"schedule_intent": True},
                            "effects": {
                                "set_visit_phone_from_sender": True,
                                "message_template": "confirm_phone",
                                "continue_loop": False,
                            },
                        },
                        {
                            "to": "awaiting_phone_confirmation",
                            "when": {"yes_no": "yes"},
                            "effects": {
                                "set_visit_phone_from_sender": True,
                                "message_template": "confirm_phone",
                                "continue_loop": False,
                            },
                        },
                        {
                            "to": "",
                            "when": {"default": True},
                            "effects": {
                                "mark_qualified": True,
                                "clear_state": True,
                                "message": "Sem problemas! Se mudar de ideia, é só me chamar. 😊\n\nPosso te ajudar com algo mais?",
                                "continue_loop": False,
                            },
                        },
                    ],
                }
            )
            continue

        if stage == "awaiting_phone_confirmation":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.prompt_and_branch",
                    "prompt": "Está correto? Se preferir outro número, pode me informar agora.",
                    "transitions": [
                        {
                            "to": "awaiting_visit_date",
                            "when": {"yes_no": "yes"},
                            "effects": {"message_template": "request_visit_date", "continue_loop": False},
                        },
                        {
                            "to": "awaiting_phone_input",
                            "when": {"yes_no": "no"},
                            "effects": {"message_template": "request_alternative_phone", "continue_loop": False},
                        },
                        {
                            "to": "awaiting_phone_input",
                            "when": {"default": True},
                            "effects": {"message_template": "request_alternative_phone", "continue_loop": False},
                        },
                    ],
                }
            )
            continue

        if stage == "awaiting_phone_input":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_phone",
                    "prompt": "Por favor, me informe um número de telefone para contato (com DDD):",
                    "config": {
                        "phone_field": "visit_phone",
                        "valid_to": "awaiting_visit_date",
                        "confirm_existing_to": "awaiting_visit_date",
                    },
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_visit_date":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_date",
                    "prompt": "Ótimo! Quando você gostaria de fazer a visita? 📅\n\nPode ser algo como: 'amanhã', 'sexta', '10/01'.",
                    "config": {"valid_to": "awaiting_visit_time"},
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_visit_time":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_time",
                    "prompt": "Perfeito! Qual horário você prefere? 🕒\n\nExemplos: '14h', '14:30', 'manhã', 'tarde'.",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_purpose":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_purpose",
                    "prompt": "Para começar, você quer:\n\n1️⃣ *Comprar* um imóvel\n2️⃣ *Alugar* um imóvel\n\nDigite 1 ou 2, ou escreva 'comprar' ou 'alugar'.",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_type":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_property_type",
                    "prompt": "Agora me diga, que tipo de imóvel você prefere:\n\n1️⃣ *Casa*\n2️⃣ *Apartamento*\n3️⃣ *Comercial*\n4️⃣ *Terreno*\n\nDigite o número ou o nome do tipo.",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_price_min":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_price_min",
                    "prompt": "Qual o valor *mínimo* que você considera?\n\n💡 Exemplos: '200000', '200 mil', '200k'",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_price_max":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_price_max",
                    "prompt": "E qual o valor *máximo*?\n\n💡 Exemplos: '500000', '500 mil', '500k'",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_bedrooms":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_bedrooms",
                    "prompt": "Ótimo! Quantos quartos você precisa?\n\n💡 Exemplos: '2', '3 quartos', 'tanto faz'",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_city":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_city",
                    "prompt": "Perfeito! Em qual cidade você está procurando?",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_neighborhood":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.capture_neighborhood",
                    "prompt": "Você tem preferência por algum *bairro*? (ou 'não')",
                    "transitions": [],
                }
            )
            continue

        if stage == "searching":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.execute_search",
                    "transitions": [],
                }
            )
            continue

        if stage == "showing_property":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.show_property_card",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_property_feedback":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.property_feedback_decision",
                    "transitions": [],
                }
            )
            continue

        if stage == "awaiting_refinement":
            nodes.append(
                {
                    "id": stage,
                    "type": "real_estate.refinement_decision",
                    "transitions": [],
                }
            )
            continue

        nodes.append({"id": stage, "type": "handler", "handler": handler, "transitions": []})
    # Adicionar transição default para o start node
    for node in nodes:
        if node["id"] == "start":
            node["transitions"] = [{"to": "awaiting_lgpd_consent"}]
            break
    return nodes

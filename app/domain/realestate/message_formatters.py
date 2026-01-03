"""
Formatadores de mensagens para o chatbot.
Responsabilidade: Construção de mensagens amigáveis e profissionais.
"""
from datetime import datetime
from typing import Dict, Any, List


def get_greeting_by_time() -> str:
    """Retorna saudação baseada no horário."""
    try:
        h = datetime.now().hour
        if 5 <= h < 12:
            return "Bom dia"
        if 12 <= h < 18:
            return "Boa tarde"
        return "Boa noite"
    except:
        return "Olá"


def format_welcome_message() -> str:
    """Mensagem de boas-vindas com LGPD."""
    saud = get_greeting_by_time()
    return (
        f"{saud}! Eu sou o assistente virtual da ND Imóveis e estou aqui para ajudar você a encontrar o imóvel ideal. 😊\n\n"
        "Para começar e para garantir a segurança dos seus dados, em conformidade com a Lei Geral de Proteção de Dados (LGPD), "
        "preciso do seu consentimento para continuar nosso atendimento.\n\n"
        "Você pode simplesmente responder 'sim' ou 'autorizo' para prosseguirmos."
    )


def format_property_card(prop_details: Dict[str, Any], purpose: str, user_name: str = "") -> str:
    """
    Formata card de imóvel individual.
    Formato: 🏢 #A738 - Apartamento 2 Quartos
             📍 Bairro Jardins, São Paulo-SP
             💰 R$ 3.000,00/mês
    """
    tipo_map = {
        "apartment": "Apartamento",
        "house": "Casa",
        "commercial": "Comercial",
        "land": "Terreno"
    }
    tipo_txt = tipo_map.get(prop_details["tipo"], prop_details["tipo"])
    
    quartos = prop_details.get('dormitorios')
    quartos_txt = f"{quartos} Quarto{'s' if quartos != 1 else ''}" if quartos else ""
    
    codigo = prop_details.get("ref_code") or prop_details.get("external_id") or prop_details["id"]
    purpose_symbol = "💰" if purpose == "sale" else "🏠"
    
    # Formatação de preço brasileiro
    price = prop_details['preco']
    price_txt = f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if purpose == "rent":
        price_txt += "/mês"
    
    bairro = prop_details.get('bairro') or 'Centro'
    cidade = prop_details['cidade']
    estado = prop_details['estado']
    
    name_prefix = f"{user_name}, " if user_name else ""
    msg_lines = [
        f"🏢 *#{codigo} - {tipo_txt} {quartos_txt}*",
        f"📍 {bairro}, {cidade}-{estado}",
        f"{purpose_symbol} {price_txt}",
        "",
        f"{name_prefix}*gostou deste imóvel?* Digite 'sim' para mais detalhes, 'próximo' para ver outra opção, 'ajustar critérios' para refinar a busca ou 'não encontrei imóvel' para encerrar."
    ]
    
    return "\n".join(msg_lines)


def format_property_details(prop_details: Dict[str, Any], user_name: str = "") -> str:
    """Formata detalhes completos do imóvel."""
    descricao = prop_details.get("descricao") or "Sem descrição disponível."
    if descricao and len(descricao) > 300:
        descricao = descricao[:297] + "..."
    
    images = prop_details.get("images", [])
    has_images = len(images) > 0
    
    name_prefix = f"{user_name}, " if user_name else ""
    msg_lines = [
        "*Detalhes Completos:*\n",
        f"📋 *Descrição:*",
        descricao,
        "",
        f"🛌️ Quartos: {prop_details.get('dormitorios', '-')}",
        f"🚿 Banheiros: {prop_details.get('banheiros', '-')}",
        f"🚗 Vagas: {prop_details.get('vagas', '-')}",
        f"📏 Área: {prop_details.get('area_total', '-')} m²",
        "",
    ]
    
    # Aviso sobre imagens
    if not has_images:
        msg_lines.append("📸 *Fotos:* Mais detalhes e imagens disponíveis através de agendamento com um profissional.\n")
    elif len(images) >= 3:
        msg_lines.append("📸 *Mais imagens disponíveis através de agendamento com um profissional.*\n")
    
    msg_lines.append(
        f"{name_prefix}*gostaria de agendar uma visita?* Digite 'agendar', 'próximo' para ver outras opções, 'ajustar critérios' para refinar a busca ou 'não encontrei imóvel' para encerrar."
    )
    
    return "\n".join(msg_lines)


def format_no_results_message(city: str, user_name: str = "") -> str:
    """Mensagem quando não há resultados."""
    name_prefix = f"{user_name}, " if user_name else ""
    return (
        f"{name_prefix}infelizmente não encontrei imóveis disponíveis com esses critérios em {city}. 😔\n\n"
        "Mas fique tranquilo! Salvei suas preferências e assim que tivermos uma opção que combine com o que você procura, "
        "entraremos em contato. 📲\n\n"
        "Gostaria de buscar em outra cidade ou ajustar os critérios?"
    )


def format_end_of_results_message(user_name: str = "") -> str:
    """Mensagem quando acabam os imóveis."""
    name_prefix = f"{user_name}, " if user_name else ""
    return (
        f"{name_prefix}esses foram todos os imóveis que encontrei com seus critérios. 🏠\n\n"
        "Gostou de algum? Se quiser, posso buscar com outros critérios ou você pode me informar "
        "qual imóvel te interessou mais para agendarmos uma visita!"
    )


def format_no_more_properties(user_name: str = "") -> str:
    """Mensagem quando não há mais imóveis para mostrar."""
    name_prefix = f"{user_name}, " if user_name else ""
    return (
        f"{name_prefix}esses foram todos os imóveis disponíveis com seus critérios de busca. 🏠\n\n"
        "Gostaria de *ajustar os critérios* para ver mais opções ou posso te ajudar com algo mais?"
    )


def format_schedule_confirmation(name: str) -> str:
    """Mensagem de confirmação de agendamento."""
    first_name = name.split()[0]
    return (
        f"Perfeito, {first_name}! ✅\n\n"
        "Seus dados foram registrados e nossa equipe entrará em contato em breve para confirmar "
        "o melhor horário para sua visita.\n\n"
        "Nosso horário de atendimento é de segunda a sexta, das 9h às 19h. 📞\n\n"
        "Obrigado pelo interesse! Até logo! 👋"
    )


def format_directed_property_intro(codigo: str) -> str:
    """Mensagem para lead direcionado."""
    return (
        f"Olá! Vi que você tem interesse no imóvel *#{codigo}*. 🏠\n\n"
        "Vou te mostrar todos os detalhes! Mas antes, preciso do seu consentimento para continuar.\n\n"
        "Você autoriza o uso dos seus dados conforme a LGPD? (responda 'sim')"
    )


# ===== FLUXO DIRECIONADO =====

def format_has_property_in_mind(user_name: str) -> str:
    """Pergunta se o cliente já tem um imóvel específico em mente."""
    return (
        f"Prazer, {user_name}! 😊\n\n"
        "*Você já viu algum imóvel específico que te interessou?*\n\n"
        "1️⃣ *Sim* - Já tenho um código/referência\n"
        "2️⃣ *Não* - Quero que você me ajude a buscar\n\n"
        "Digite 1 ou 2, ou escreva 'sim' ou 'não'."
    )


def format_request_property_code() -> str:
    """Solicita código do imóvel."""
    return (
        "Ótimo! 🎯\n\n"
        "Por favor, me informe o *código do imóvel* que você viu.\n"
        "Pode ser algo como: A1234, ND12345, ou apenas o número."
    )


def format_property_not_found(codigo: str) -> str:
    """Mensagem quando imóvel não é encontrado."""
    return (
        f"Hmm... não encontrei o imóvel com o código *{codigo}* no nosso sistema. 😕\n\n"
        "Você pode:\n"
        "• Verificar se digitou o código corretamente\n"
        "• Tentar outro código\n"
        "• Ou dizer 'não' para eu te ajudar a buscar imóveis"
    )


def format_property_found_details(prop: Dict[str, Any]) -> str:
    """Mostra detalhes do imóvel encontrado."""
    tipo_map = {
        "apartment": "Apartamento",
        "house": "Casa",
        "commercial": "Comercial",
        "land": "Terreno"
    }
    tipo = tipo_map.get(prop.get("tipo"), prop.get("tipo", "Imóvel"))
    
    codigo = prop.get("ref_code") or prop.get("id")
    preco = prop.get("preco", 0)
    preco_fmt = f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    quartos = prop.get("dormitorios")
    banheiros = prop.get("banheiros")
    vagas = prop.get("vagas")
    area = prop.get("area_total")
    
    bairro = prop.get("bairro", "")
    cidade = prop.get("cidade", "")
    estado = prop.get("estado", "")
    
    descricao = prop.get("descricao", "")
    if descricao and len(descricao) > 200:
        descricao = descricao[:197] + "..."
    
    msg = [
        f"🏠 *{tipo} - Código #{codigo}*\n",
        f"📍 {bairro}, {cidade}-{estado}",
        f"💰 {preco_fmt}\n",
    ]
    
    if quartos:
        msg.append(f"🛏️ {quartos} quarto(s)")
    if banheiros:
        msg.append(f"🚿 {banheiros} banheiro(s)")
    if vagas:
        msg.append(f"🚗 {vagas} vaga(s)")
    if area:
        msg.append(f"📏 {area} m²")
    
    if descricao:
        msg.append(f"\n📋 {descricao}")
    
    msg.append("\n*Tem alguma dúvida sobre este imóvel?*")
    
    return "\n".join(msg)


def format_ask_schedule_visit() -> str:
    """Pergunta se quer agendar visita."""
    return "Gostaria de agendar uma visita para conhecer o imóvel pessoalmente? 📅"


def format_confirm_phone(phone: str) -> str:
    """Confirma telefone para contato."""
    return (
        f"Perfeito! Vou usar este número para contato: *{phone}*\n\n"
        "Está correto? Se preferir outro número, pode me informar agora."
    )


def format_request_alternative_phone() -> str:
    """Solicita telefone alternativo."""
    return "Por favor, me informe um número de telefone para contato (com DDD):"


def format_invalid_phone() -> str:
    """Mensagem de telefone inválido."""
    return (
        "Hmm... esse número não parece válido. 🤔\n\n"
        "Por favor, informe um número com DDD, exemplo: (11) 98765-4321"
    )


def format_request_visit_date() -> str:
    """Solicita data da visita."""
    return (
        "Ótimo! Quando você gostaria de fazer a visita? 📅\n\n"
        "Você pode dizer:\n"
        "• 'amanhã'\n"
        "• 'segunda-feira'\n"
        "• Ou uma data específica (ex: 25/10)"
    )


def format_invalid_date() -> str:
    """Mensagem de data inválida."""
    return (
        "Desculpe, não consegui entender essa data. 😕\n\n"
        "Tente novamente com:\n"
        "• 'amanhã' ou 'hoje'\n"
        "• Dia da semana (ex: 'segunda')\n"
        "• Data no formato DD/MM (ex: '25/10')"
    )


def format_request_visit_time() -> str:
    """Solicita horário da visita."""
    return (
        "E qual horário prefere? ⏰\n\n"
        "Você pode dizer:\n"
        "• 'manhã' (9h-12h)\n"
        "• 'tarde' (14h-18h)\n"
        "• Ou um horário específico (ex: '15h' ou '15:30')"
    )


def format_invalid_time() -> str:
    """Mensagem de horário inválido."""
    return (
        "Não consegui entender esse horário. 😕\n\n"
        "Tente:\n"
        "• 'manhã' ou 'tarde'\n"
        "• Horário específico (ex: '14h' ou '14:30')"
    )


def format_past_time_error(time_str: str) -> str:
    """Mensagem quando o horário escolhido já passou."""
    return (
        f"O horário das {time_str} de hoje já passou. 😕\n\n"
        f"Por favor, escolha um horário futuro."
    )


def format_visit_scheduled(name: str, date_str: str, time_str: str, property_code: str) -> str:
    """Confirma agendamento da visita."""
    first_name = name.split()[0]
    return (
        f"✅ *Visita agendada com sucesso!*\n\n"
        f"👤 Nome: {name}\n"
        f"🏠 Imóvel: #{property_code}\n"
        f"📅 Data: {date_str}\n"
        f"⏰ Horário: {time_str}\n\n"
        f"Perfeito, {first_name}! Nossa equipe entrará em contato para confirmar os detalhes.\n\n"
        "Obrigado pelo interesse! 🎉"
    )


def format_no_match_final(user_name: str = "") -> str:
    name_prefix = f"{user_name}, " if user_name else ""
    return (
        f"{name_prefix}salvei suas preferências e vou avisar quando surgir algo no seu perfil. 🙌\n\n"
        "Se quiser, podemos ajustar os critérios no futuro. Obrigado pelo seu tempo!"
    )

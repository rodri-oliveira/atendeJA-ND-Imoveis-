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


def format_property_card(prop_details: Dict[str, Any], purpose: str) -> str:
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
    
    msg_lines = [
        f"🏢 *#{codigo} - {tipo_txt} {quartos_txt}*",
        f"📍 {bairro}, {cidade}-{estado}",
        f"{purpose_symbol} {price_txt}",
        "",
        "*Gostou deste imóvel?* Digite 'sim' para mais detalhes ou 'próximo' para ver outra opção."
    ]
    
    return "\n".join(msg_lines)


def format_property_details(prop_details: Dict[str, Any]) -> str:
    """Formata detalhes completos do imóvel."""
    descricao = prop_details.get("descricao", "Sem descrição disponível.")
    if len(descricao) > 300:
        descricao = descricao[:297] + "..."
    
    msg_lines = [
        "*Detalhes Completos:*\n",
        f"📋 *Descrição:*",
        descricao,
        "",
        f"🛏️ Quartos: {prop_details.get('dormitorios', '-')}",
        f"🚿 Banheiros: {prop_details.get('banheiros', '-')}",
        f"🚗 Vagas: {prop_details.get('vagas', '-')}",
        f"📐 Área: {prop_details.get('area_total', '-')} m²",
        "",
        "*Gostaria de agendar uma visita?* Digite 'agendar' ou 'próximo' para ver outras opções."
    ]
    
    return "\n".join(msg_lines)


def format_no_results_message(city: str) -> str:
    """Mensagem quando não há resultados."""
    return (
        f"Infelizmente não encontrei imóveis disponíveis com esses critérios em {city}. 😔\n\n"
        "Mas fique tranquilo! Salvei suas preferências e assim que tivermos uma opção que combine com o que você procura, "
        "entraremos em contato. 📲\n\n"
        "Gostaria de buscar em outra cidade ou ajustar os critérios?"
    )


def format_end_of_results_message() -> str:
    """Mensagem quando acabam os imóveis."""
    return (
        "Esses foram todos os imóveis que encontrei com seus critérios. 🏠\n\n"
        "Gostou de algum? Se quiser, posso buscar com outros critérios ou você pode me informar "
        "qual imóvel te interessou mais para agendarmos uma visita!"
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

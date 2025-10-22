"""
MCP (Model Context Protocol) - Orquestrador de Conversação.
Responsabilidade: Roteamento de requisições e coordenação de handlers.
"""
from typing import Any, Dict, List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_conversation_state_service
from app.services.conversation_state import ConversationStateService
from app.core.config import settings
from app.domain.realestate.models import Property, PropertyImage, PropertyType, PropertyPurpose
from app.domain.realestate.conversation_handlers import ConversationHandler
from app.services.lead_service import LeadService
from app.services.llm_service import get_llm_service
from app.domain.realestate import detection_utils as detect

router = APIRouter()


# --- Dep ---
# Centralizado via app.api.deps.get_db


# --- Schemas ---

class MCPRequest(BaseModel):
    input: str = Field(..., description="Entrada do usuário (texto livre)")
    sender_id: str = Field(..., description="ID único do remetente (ex: número do WhatsApp)")
    tenant_id: str = Field(default_factory=lambda: settings.DEFAULT_TENANT_ID)
    tools_allow: Optional[List[str]] = Field(default=None, description="Lista de tools permitidas (whitelist)")
    mode: str = Field(default="auto", description="auto|tool")
    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input": "Quero alugar apartamento 2 quartos em São Paulo até 3500",
                    "mode": "auto"
                },
                {
                    "input": "",
                    "mode": "tool",
                    "tool": "buscar_imoveis",
                    "params": {
                        "finalidade": "rent",
                        "tipo": "apartment",
                        "cidade": "São Paulo",
                        "estado": "SP",
                        "dormitorios_min": 2,
                        "preco_max": 3500,
                        "limit": 5
                    }
                },
                {
                    "input": "",
                    "mode": "tool",
                    "tool": "detalhar_imovel",
                    "params": {"imovel_id": 1}
                },
                
            ]
        }
    }


class MCPToolCall(BaseModel):
    tool: str
    params: Dict[str, Any]
    result: Any


class MCPResponse(BaseModel):
    message: str
    tool_calls: List[MCPToolCall] = []
    media: List[str] = []  # URLs de imagens/vídeos para enviar


# --- Auth ---

def _check_auth(authorization: Optional[str]):
    if not settings.MCP_API_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    token = authorization.split(" ", 1)[1]
    if token != settings.MCP_API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_token")


# --- Tools ---

def t_buscar_imoveis(db: Session, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    stmt = select(Property).where(Property.is_active == True)  # noqa: E712
    m = params or {}
    if m.get("finalidade"):
        stmt = stmt.where(Property.purpose == PropertyPurpose(m["finalidade"]))
    if m.get("tipo"):
        stmt = stmt.where(Property.type == PropertyType(m["tipo"]))
    if m.get("cidade"):
        stmt = stmt.where(Property.address_city.ilike(m["cidade"]))
    if m.get("estado"):
        stmt = stmt.where(Property.address_state == m["estado"]) 
    if m.get("preco_min") is not None:
        stmt = stmt.where(Property.price >= float(m["preco_min"]))
    if m.get("preco_max") is not None:
        stmt = stmt.where(Property.price <= float(m["preco_max"]))
    if m.get("dormitorios_min") is not None:
        stmt = stmt.where(Property.bedrooms >= int(m["dormitorios_min"]))
    limit = int(m.get("limit", 5))
    stmt = stmt.limit(min(max(limit,1), 20))
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "ref_code": getattr(r, "ref_code", None),
            "external_id": getattr(r, "external_id", None),
            "titulo": r.title,
            "tipo": r.type.value,
            "finalidade": r.purpose.value,
            "preco": r.price,
            "cidade": r.address_city,
            "estado": r.address_state,
            "dormitorios": r.bedrooms,
        }
        for r in rows
    ]


def t_detalhar_imovel(db: Session, imovel_id: int) -> Dict[str, Any]:
    p = db.get(Property, imovel_id)
    if not p:
        raise HTTPException(status_code=404, detail="property_not_found")
    imgs_stmt = (
        select(PropertyImage)
        .where(PropertyImage.property_id == imovel_id)
        .order_by(PropertyImage.is_cover.desc(), PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    )
    imgs = db.execute(imgs_stmt).scalars().all()
    return {
        "id": p.id,
        "ref_code": getattr(p, "ref_code", None),
        "external_id": getattr(p, "external_id", None),
        "titulo": p.title,
        "descricao": p.description,
        "tipo": p.type.value,
        "finalidade": p.purpose.value,
        "preco": p.price,
        "cidade": p.address_city,
        "estado": p.address_state,
        "bairro": p.address_neighborhood,
        "dormitorios": p.bedrooms,
        "banheiros": p.bathrooms,
        "suites": p.suites,
        "vagas": p.parking_spots,
        "area_total": p.area_total,
        "area_util": p.area_usable,
        "imagens": [
            {"id": i.id, "url": i.url, "is_capa": i.is_cover, "ordem": i.sort_order} for i in imgs
        ],
    }


def t_criar_lead(db: Session, dados: Dict[str, Any]) -> Dict[str, Any]:
    """Cria lead usando LeadService."""
    lead = LeadService.create_lead(db, dados)
    return {"id": lead.id, "nome": lead.name, "telefone": lead.phone}


TOOLS = {
    "buscar_imoveis": {"fn": t_buscar_imoveis},
    "detalhar_imovel": {"fn": t_detalhar_imovel},
    "criar_lead": {"fn": t_criar_lead},
}


def _whitelist_ok(name: str, allow: Optional[List[str]]) -> bool:
    """Verifica se tool está na whitelist."""
    if not allow:
        return True
    return name in allow


@router.post(
    "/execute",
    response_model=MCPResponse,
    summary="Executa agente MCP (MVP)",
    description="Modo auto interpreta o texto do usuário; modo tool executa uma ferramenta específica. Use Authorization: Bearer <token> se MCP_API_TOKEN estiver definido."
)
async def execute_mcp(
    body: MCPRequest,
    db: Annotated[Session, Depends(get_db)],
    state_service: Annotated[ConversationStateService, Depends(get_conversation_state_service)],
    Authorization: Optional[str] = Header(default=None),
):
    _check_auth(Authorization)

    tool_calls: List[MCPToolCall] = []

    # Modo explícito de tool
    if body.mode == "tool":
        if not body.tool:
            raise HTTPException(status_code=400, detail="tool_required")
        if not _whitelist_ok(body.tool, body.tools_allow):
            raise HTTPException(status_code=403, detail="tool_not_allowed")
        if body.tool not in TOOLS:
            raise HTTPException(status_code=404, detail="tool_not_found")
        fn = TOOLS[body.tool]["fn"]
        if body.tool == "detalhar_imovel":
            res = fn(db, int((body.params or {}).get("imovel_id")))
        elif body.tool == "buscar_imoveis":
            res = fn(db, body.params or {})
        elif body.tool == "criar_lead":
            res = fn(db, body.params or {})
        else:
            res = None
        tool_calls.append(MCPToolCall(tool=body.tool, params=body.params or {}, result=res))
        return MCPResponse(message="tool_executed", tool_calls=tool_calls)

    # Modo auto (stateful) - Arquitetura Modular
    text_raw = body.input or ""
    text = text_raw.lower()
    state = state_service.get_state(body.sender_id) or {}
    
    # DEBUG: Log do estado atual
    import structlog
    log = structlog.get_logger()
    log.info("=" * 60)
    log.info("🔵 MCP REQUEST", sender_id=body.sender_id, input=text_raw, current_stage=state.get("stage", "start"), state_keys=list(state.keys()))
    log.info("=" * 60)
    
    handler = ConversationHandler(db)
    
    # ===== PRÉ-PROCESSAMENTO LLM (UMA VEZ, ANTES DO LOOP) =====
    # Extrai intenção e entidades da mensagem do usuário
    # Armazena no state para uso pelos handlers
    if text_raw.strip():
        try:
            llm = get_llm_service()
            llm_result = await llm.extract_intent_and_entities(text_raw)
            if isinstance(llm_result, dict):
                state["llm_intent"] = llm_result.get("intent")
                state["llm_entities"] = llm_result.get("entities") or {}
                log.info("✅ LLM extraction", intent=state.get("llm_intent"), entities=state.get("llm_entities"))
        except Exception as e:
            log.warning("⚠️ LLM preparse failed", error=str(e))
            # Continua sem LLM - handlers usarão fallback regex
    
    # ===== LOOP DE CONVERSAÇÃO =====
    # Permite transições de estado internas sem reprocessar LLM
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        stage = state.get("stage", "start")
        log.debug("mcp_stage", iteration=iteration, stage=stage, state_keys=list(state.keys()))
        
        # ===== INTERCEPTOR: COMANDOS GLOBAIS =====
        # Processa apenas comandos que NÃO precisam de contexto
        if text_raw.strip():
            # Comando: AJUDA (único comando global - resto vai para LLM)
            if detect.detect_help_command(text_raw):
                msg = (
                    "📋 *Comandos disponíveis:*\n\n"
                    "• *ajuda* - Mostra esta mensagem\n"
                    "• *próximo* - Vê o próximo imóvel\n"
                    "• *sim* - Confirma interesse\n"
                    "• *não* - Recusa ou pula etapa\n\n"
                    f"📍 *Você está em:* {stage.replace('_', ' ').title()}\n\n"
                    "Continue de onde parou!"
                )
                return MCPResponse(message=msg, tool_calls=tool_calls)
        
        # Roteamento para handlers específicos
        if stage == "start":
            msg, state, continue_loop = handler.handle_start(text_raw, state)
        elif stage == "awaiting_lgpd_consent":
            msg, state, continue_loop = handler.handle_lgpd_consent(text, state)
        elif stage == "awaiting_name":
            msg, state, continue_loop = handler.handle_name(text, state)
        elif stage == "awaiting_purpose":
            msg, state, continue_loop = handler.handle_purpose(text, state)
        elif stage == "awaiting_city":
            msg, state, continue_loop = handler.handle_city(text_raw, state)
        elif stage == "awaiting_type":
            msg, state, continue_loop = handler.handle_type(text, state)
        elif stage == "awaiting_price_min":
            msg, state, continue_loop = handler.handle_price_min(text, state)
        elif stage == "awaiting_price_max":
            msg, state, continue_loop = handler.handle_price_max(text, state)
        elif stage == "awaiting_bedrooms":
            msg, state, continue_loop = handler.handle_bedrooms(text, state)
        elif stage == "awaiting_neighborhood":
            msg, state, continue_loop = handler.handle_neighborhood(text_raw, state)
        elif stage == "searching":
            msg, state, continue_loop = handler.handle_searching(body.sender_id, state)
        elif stage == "showing_property":
            msg, state, continue_loop = handler.handle_showing_property(state)
        elif stage == "awaiting_property_feedback":
            msg, state, continue_loop = handler.handle_property_feedback(text, state)
        elif stage == "awaiting_visit_decision":
            msg, state, continue_loop = handler.handle_visit_decision(text, state)
        elif stage == "collecting_name":
            msg, state, continue_loop = handler.handle_collecting_name(text_raw, state)
        elif stage == "collecting_email":
            msg, state, continue_loop = handler.handle_collecting_email(text_raw, body.sender_id, state)
        elif stage == "awaiting_refinement":
            msg, state, continue_loop = handler.handle_refinement(text, state)
        else:
            # Estágio desconhecido - fallback
            break
        
        # Atualizar state no Redis
        if state:
            log.info("saving_state_to_redis", 
                     sender_id=body.sender_id,
                     stage=state.get("stage"),
                     state_keys=list(state.keys()),
                     has_purpose=bool(state.get("purpose")),
                     has_type=bool(state.get("type")),
                     has_city=bool(state.get("city")))
            state_service.set_state(body.sender_id, state)
        else:
            state_service.clear_state(body.sender_id)
        
        # Se há mensagem, retornar
        if msg:
            # Extrair imagens do state (se houver)
            media_urls = state.get("property_detail_images", [])
            if media_urls:
                # Limpar imagens do state após extrair (para não reenviar)
                state.pop("property_detail_images", None)
                state_service.set_state(body.sender_id, state)
            return MCPResponse(message=msg, tool_calls=tool_calls, media=media_urls)
        
        # Se não deve continuar loop, sair
        if not continue_loop:
            break
        
        # Limpar texto para próxima iteração
        text = ""
        text_raw = ""

    # Fallback: se chegou aqui, algo não foi tratado
    state_service.clear_state(body.sender_id)
    msg_fallback = "Desculpe, não entendi. Para começar, me diga: você quer *comprar* ou *alugar* um imóvel?"
    return MCPResponse(message=msg_fallback, tool_calls=tool_calls)


# ===== Admin: limpar estado de conversas (DEV only) =====
class ClearStateIn(BaseModel):
    sender_ids: List[str]


@router.post("/admin/state/clear")
def mcp_admin_clear_state(
    payload: ClearStateIn,
    state_service: Annotated[ConversationStateService, Depends(get_conversation_state_service)],
    Authorization: Optional[str] = Header(default=None),
):
    """Limpa o estado de conversa para os sender_ids informados. Protegido por MCP_API_TOKEN.
    Uso destinado a desenvolvimento/auto-teste.
    """
    _check_auth(Authorization)
    sender_ids = [s for s in (payload.sender_ids or []) if str(s).strip()]
    cleared = 0
    for sid in sender_ids:
        try:
            state_service.clear_state(sid)
            cleared += 1
        except Exception:
            # ignora erros por sender_id inexistente
            pass
    return {"ok": True, "cleared": cleared}

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.services.conversation_context import normalize_state
from app.services.conversation_state import ConversationStateService
from app.services.flow_engine import FlowEngine


@dataclass
class FlowOrchestrationResult:
    message: str
    state: Dict[str, Any]
    handled: bool
    continue_loop: bool


def try_process_via_flow_engine(
    *,
    db: Session,
    state_service: ConversationStateService,
    sender_id: str,
    tenant_id: int,
    domain: str,
    text_raw: str,
    text_normalized: str,
    initial_state: Optional[Dict[str, Any]] = None,
    persist_state: bool = True,
) -> FlowOrchestrationResult:
    loaded = initial_state or (state_service.get_state(sender_id, tenant_id=int(tenant_id)) or {})
    state = normalize_state(state=loaded, sender_id=sender_id, tenant_id=int(tenant_id), default_stage="start")

    flow_engine = FlowEngine(db)
    flow_result = flow_engine.try_process_message(
        sender_id=sender_id,
        tenant_id=int(tenant_id),
        domain=domain,
        text_raw=text_raw,
        text_normalized=text_normalized,
        state=state,
    )

    if not flow_result.handled:
        return FlowOrchestrationResult(message="", state=state, handled=False, continue_loop=False)

    out_state = flow_result.state or state
    if persist_state:
        state_service.set_state(sender_id, out_state, tenant_id=int(tenant_id))
    return FlowOrchestrationResult(
        message=flow_result.message,
        state=out_state,
        handled=True,
        continue_loop=bool(flow_result.continue_loop),
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.realestate.chatbot_flow_schema import ChatbotFlowDefinitionV1, FlowNodeV1
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.domain.chatbot.handler_factory import get_conversation_handler_for_domain
from app.domain.realestate import detection_utils as detect
from app.domain.realestate import message_formatters as fmt
from app.domain.realestate.models import Lead, Property, PropertyImage, PropertyPurpose, PropertyType
from app.domain.catalog.models import CatalogItem, CatalogItemType
from app.domain.realestate.validation_utils import validate_bedrooms, validate_city, validate_price
from app.services.lead_service import LeadService
from app.services.visit_service import VisitService
from app.services.notification_service import NotificationService


@dataclass
class FlowEngineResult:
    message: str
    state: Dict[str, Any]
    continue_loop: bool
    handled: bool


class FlowEngine:
    """Execução de Flow-as-Data com fallback seguro para o ConversationHandler.

    Estratégia V1:
    - Carrega flow publicado por tenant+domain
    - Executa apenas nodes do tipo 'handler'
    - 'handler' mapeia para métodos do ConversationHandler (handle_<handler>)

    A intenção é ser incremental e anti-regressão.
    """

    def __init__(self, db: Session):
        self.db = db
        self._flow_service = ChatbotFlowService(db=db)
        self._handler = None

    def try_process_message(
        self,
        *,
        sender_id: str,
        tenant_id: int,
        domain: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> FlowEngineResult:
        """Tenta processar via Flow Engine. Se não houver flow válido, retorna handled=False."""

        flow_row = self._flow_service.get_published_flow(tenant_id=tenant_id, domain=domain)
        if not flow_row:
            return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

        try:
            flow = self._flow_service.validate_definition(flow_row.flow_definition)
        except Exception:
            return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

        return self._try_process_with_flow(
            flow=flow,
            sender_id=sender_id,
            domain=domain,
            text_raw=text_raw,
            text_normalized=text_normalized,
            state=state,
        )

    def try_process_message_with_definition(
        self,
        *,
        flow_definition: Dict[str, Any],
        domain: str,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> FlowEngineResult:
        """Executa um flow fornecido (ex.: preview de draft) sem depender de published flow."""

        try:
            flow = self._flow_service.validate_definition(flow_definition)
        except Exception:
            return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

        return self._try_process_with_flow(
            flow=flow,
            sender_id=sender_id,
            domain=(domain or "").strip() or "real_estate",
            text_raw=text_raw,
            text_normalized=text_normalized,
            state=state,
        )

    def _try_process_with_flow(
        self,
        *,
        flow: ChatbotFlowDefinitionV1,
        sender_id: str,
        domain: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> FlowEngineResult:
        stage = (state.get("stage") or flow.start or "start").strip()
        node = self._resolve_node(flow, stage)
        if not node:
            return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

        if node.type == "static_message":
            msg, new_state, continue_loop = self._process_static_message(node=node, state=state)
        elif node.type == "end":
            msg, new_state, continue_loop = self._process_end(node=node, state=state)
        elif node.type == "set_state":
            msg, new_state, continue_loop = self._process_set_state(node=node, state=state)
        elif node.type == "capture_text":
            msg, new_state, continue_loop = self._process_capture_text(node=node, text_raw=text_raw, state=state)
        elif node.type == "capture_number":
            msg, new_state, continue_loop = self._process_capture_number(node=node, text_raw=text_raw, state=state)
        elif node.type == "capture_phone_generic":
            msg, new_state, continue_loop = self._process_capture_phone_generic(node=node, text_raw=text_raw, state=state)
        elif node.type == "execute_vehicle_search":
            msg, new_state, continue_loop = self._process_execute_vehicle_search(node=node, state=state)
        elif node.type == "handler":
            if not node.handler:
                return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

            # O handler do legacy usa text_raw em alguns pontos e text_normalized em outros.
            # Para evitar regressão, aplicamos um mapeamento conservador por handler.
            msg, new_state, continue_loop = self._call_legacy_handler(
                handler_name=node.handler,
                sender_id=sender_id,
                domain=domain,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "prompt_and_branch":
            msg, new_state, continue_loop = self._process_prompt_and_branch(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_phone":
            msg, new_state, continue_loop = self._process_capture_phone(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_date":
            msg, new_state, continue_loop = self._process_capture_date(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_time":
            msg, new_state, continue_loop = self._process_capture_time(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_purpose":
            msg, new_state, continue_loop = self._process_capture_purpose(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_property_type":
            msg, new_state, continue_loop = self._process_capture_property_type(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_price_min":
            msg, new_state, continue_loop = self._process_capture_price_min(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_price_max":
            msg, new_state, continue_loop = self._process_capture_price_max(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_bedrooms":
            msg, new_state, continue_loop = self._process_capture_bedrooms(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_city":
            msg, new_state, continue_loop = self._process_capture_city(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "capture_neighborhood":
            msg, new_state, continue_loop = self._process_capture_neighborhood(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "execute_search":
            msg, new_state, continue_loop = self._process_execute_search(
                node=node,
                sender_id=sender_id,
                state=state,
            )
        elif node.type == "show_property_card":
            msg, new_state, continue_loop = self._process_show_property_card(
                node=node,
                sender_id=sender_id,
                state=state,
            )
        elif node.type == "property_feedback_decision":
            msg, new_state, continue_loop = self._process_property_feedback_decision(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        elif node.type == "refinement_decision":
            msg, new_state, continue_loop = self._process_refinement_decision(
                node=node,
                sender_id=sender_id,
                text_raw=text_raw,
                text_normalized=text_normalized,
                state=state,
            )
        else:
            return FlowEngineResult(message="", state=state, continue_loop=False, handled=False)

        # Se o handler avançou stage automaticamente, ok.
        # Se não avançou, usamos transição default se houver.
        if not (new_state.get("stage") or "").strip():
            next_stage = self._default_transition(node)
            if next_stage:
                new_state["stage"] = next_stage

        # Em V1 a engine não implementa loop interno. Isso fica com o MCP.
        return FlowEngineResult(message=msg, state=new_state, continue_loop=bool(continue_loop), handled=True)

    def _get_by_path(self, obj: Dict[str, Any], path: str) -> Any:
        raw = (path or "").strip()
        if not raw:
            return None
        cur: Any = obj
        for part in raw.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def _set_by_path(self, obj: Dict[str, Any], path: str, value: Any) -> None:
        raw = (path or "").strip()
        if not raw:
            return
        parts = raw.split(".")
        cur: Dict[str, Any] = obj
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt
        cur[parts[-1]] = value

    def _process_static_message(self, *, node: FlowNodeV1, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        # Send prompt and advance to default transition (if any) in the same MCP request.
        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return ((node.prompt or ""), state, True)
        return ((node.prompt or ""), state, False)

    def _process_end(self, *, node: FlowNodeV1, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        # End node: optional message, then reset stage to start so next inbound can restart safely.
        # This avoids FlowEngine returning handled=False on subsequent messages.
        msg = (node.prompt or "").strip()
        state["stage"] = "start"
        state["flow_ended"] = True
        return (msg, state, False)

    def _process_set_state(self, *, node: FlowNodeV1, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}
        patch = config.get("set")
        if isinstance(patch, dict):
            for k, v in patch.items():
                if isinstance(k, str) and k.strip():
                    self._set_by_path(state, k, v)
        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return ("", state, True)
        return ("", state, False)

    def _process_capture_phone_generic(self, *, node: FlowNodeV1, text_raw: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        target = config.get("target")
        if not isinstance(target, str) or not target.strip():
            target = "car_dealer.phone"

        prompt_key = "_flow_prompt_stage"
        if state.get(prompt_key) != node.id:
            state[prompt_key] = node.id
            return ((node.prompt or ""), state, False)

        raw = "".join(ch for ch in (text_raw or "") if ch.isdigit())
        min_digits = config.get("min_digits")
        max_digits = config.get("max_digits")
        try:
            min_digits_int = int(min_digits) if min_digits is not None else 10
        except Exception:
            min_digits_int = 10
        try:
            max_digits_int = int(max_digits) if max_digits is not None else 13
        except Exception:
            max_digits_int = 13

        if len(raw) < min_digits_int or len(raw) > max_digits_int:
            invalid = config.get("invalid_message")
            if isinstance(invalid, str) and invalid.strip():
                return (invalid, state, False)
            return ((node.prompt or ""), state, False)

        self._set_by_path(state, target, raw)

        lead_status = config.get("lead_status")
        if isinstance(lead_status, str) and lead_status.strip():
            name_path = config.get("lead_name_path")
            email_path = config.get("lead_email_path")
            name = self._get_by_path(state, str(name_path)) if isinstance(name_path, str) and name_path.strip() else None
            email = self._get_by_path(state, str(email_path)) if isinstance(email_path, str) and email_path.strip() else None
            try:
                LeadService.upsert_lead_status(
                    self.db,
                    phone=raw,
                    state=state,
                    status=lead_status.strip(),
                    name=(str(name).strip() if isinstance(name, str) and str(name).strip() else None),
                    email=(str(email).strip() if isinstance(email, str) and str(email).strip() else None),
                )
            except Exception:
                pass

        state.pop(prompt_key, None)
        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return ("", state, True)
        return ("", state, False)

    def _process_capture_text(self, *, node: FlowNodeV1, text_raw: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        target = config.get("target")
        if not isinstance(target, str) or not target.strip():
            # Without target, cannot persist.
            return (node.prompt or "", state, False)

        prompt_key = "_flow_prompt_stage"
        if state.get(prompt_key) != node.id:
            state[prompt_key] = node.id
            return ((node.prompt or ""), state, False)

        val = (text_raw or "").strip()
        min_len = config.get("min_len")
        try:
            min_len_int = int(min_len) if min_len is not None else 1
        except Exception:
            min_len_int = 1
        if len(val) < max(1, min_len_int):
            return ((node.prompt or ""), state, False)

        self._set_by_path(state, target, val)
        state.pop(prompt_key, None)
        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return ("", state, True)
        return ("", state, False)

    def _process_capture_number(self, *, node: FlowNodeV1, text_raw: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        target = config.get("target")
        if not isinstance(target, str) or not target.strip():
            return (node.prompt or "", state, False)

        prompt_key = "_flow_prompt_stage"
        if state.get(prompt_key) != node.id:
            state[prompt_key] = node.id
            return ((node.prompt or ""), state, False)

        raw = (text_raw or "").strip().lower()
        cleaned = raw.replace("r$", " ").replace(".", " ").replace(",", " ")
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        if not digits:
            return ((node.prompt or ""), state, False)

        try:
            n = int(digits)
        except Exception:
            return ((node.prompt or ""), state, False)

        if bool(config.get("treat_as_thousands")) and n < 1000:
            n = n * 1000

        min_v = config.get("min")
        max_v = config.get("max")
        try:
            if min_v is not None and n < int(min_v):
                return ((node.prompt or ""), state, False)
        except Exception:
            pass
        try:
            if max_v is not None and n > int(max_v):
                return ((node.prompt or ""), state, False)
        except Exception:
            pass

        self._set_by_path(state, target, n)
        state.pop(prompt_key, None)
        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return ("", state, True)
        return ("", state, False)

    def _process_execute_vehicle_search(self, *, node: FlowNodeV1, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        tenant_id = int(state.get("tenant_id") or 0)
        if not tenant_id:
            return ("Não consegui identificar o tenant para buscar veículos.", state, False)

        query_path = config.get("query_path") or "car_dealer.query"
        budget_path = config.get("budget_max_path") or "car_dealer.budget_max"
        results_path = config.get("results_path") or "car_dealer.search_results"
        limit = config.get("limit")
        try:
            limit_int = int(limit) if limit is not None else 3
        except Exception:
            limit_int = 3
        limit_int = max(1, min(10, limit_int))

        q = str(self._get_by_path(state, str(query_path)) or "").strip().lower()
        budget_val = self._get_by_path(state, str(budget_path))
        try:
            budget_max = int(budget_val) if budget_val is not None else None
        except Exception:
            budget_max = None

        item_type = (
            self.db.query(CatalogItemType)
            .filter(CatalogItemType.tenant_id == int(tenant_id), CatalogItemType.key == "vehicle")
            .first()
        )
        if not item_type:
            self._set_by_path(state, results_path, [])
            next_stage = self._default_transition(node)
            if next_stage:
                state["stage"] = next_stage
            return ("Ainda não há catálogo de veículos configurado.", state, False)

        rows = (
            self.db.query(CatalogItem)
            .filter(
                CatalogItem.tenant_id == int(tenant_id),
                CatalogItem.item_type_id == int(item_type.id),
                CatalogItem.is_active == True,  # noqa: E712
            )
            .order_by(CatalogItem.id.desc())
            .limit(120)
            .all()
        )

        def norm(s: str) -> str:
            return " ".join((s or "").strip().lower().split())

        qn = norm(q)
        results: list[dict[str, Any]] = []
        for r in rows:
            title = str(getattr(r, "title", "") or "")
            attrs = dict(getattr(r, "attributes", {}) or {})
            hay = norm(" ".join([title, str(attrs.get("make") or ""), str(attrs.get("model") or "")]))
            if qn and qn not in hay:
                continue

            price = attrs.get("price")
            try:
                price_n = float(price) if price is not None else None
            except Exception:
                price_n = None
            if budget_max is not None and price_n is not None and price_n > float(budget_max):
                continue

            results.append(
                {
                    "id": int(r.id),
                    "title": title,
                    "price": price_n,
                    "year": attrs.get("year"),
                    "km": attrs.get("km"),
                }
            )
            if len(results) >= limit_int:
                break

        self._set_by_path(state, results_path, results)

        # Format message (or allow override in config)
        if not results:
            msg = str(config.get("empty_message") or "Não encontrei veículos com esse perfil.")
        else:
            header = str(config.get("header") or "Encontrei essas opções:")
            lines = [header]
            for idx, it in enumerate(results, start=1):
                price = it.get("price")
                price_str = f"R$ {price:,.0f}".replace(",", ".") if isinstance(price, (int, float)) else "Consulte"
                year = it.get("year")
                km = it.get("km")
                extras = []
                if year is not None:
                    extras.append(str(year))
                if km is not None:
                    try:
                        extras.append(f"{int(km):,} km".replace(",", "."))
                    except Exception:
                        extras.append(str(km))
                extra_str = " • ".join(extras)
                lines.append(f"{idx}) {it.get('title') or 'Veículo'} — {price_str}" + (f" ({extra_str})" if extra_str else ""))
            msg = "\n".join(lines)

        next_stage = self._default_transition(node)
        if next_stage:
            state["stage"] = next_stage
            return (msg, state, True)
        return (msg, state, False)

    def _resolve_node(self, flow: ChatbotFlowDefinitionV1, node_id: str) -> Optional[FlowNodeV1]:
        by_id = flow.node_by_id()
        return by_id.get(node_id)

    def _default_transition(self, node: FlowNodeV1) -> Optional[str]:
        if not node.transitions:
            return None
        return node.transitions[0].to

    def _call_legacy_handler(
        self,
        *,
        handler_name: str,
        sender_id: str,
        domain: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        handler = get_conversation_handler_for_domain(domain=domain, db=self.db)
        fn_name = f"handle_{handler_name}".strip()
        fn = getattr(handler, fn_name, None)
        if not fn:
            return ("", state, False)

        # handlers que no legacy usavam raw
        raw_handlers = {
            "start",
            "city",
            "neighborhood",
        }

        # handlers que não recebem texto
        state_only_handlers = {
            "showing_property",
            "show_directed_property",
        }

        # handlers que recebem sender_id (e não texto)
        sender_only_handlers = {
            "searching",
        }

        # handlers que precisam de text + sender_id
        text_sender_handlers = {
            "visit_time",
            "visit_decision",
        }

        if handler_name in raw_handlers:
            return fn(text_raw, state)
        if handler_name in state_only_handlers:
            return fn(state)
        if handler_name in sender_only_handlers:
            return fn(sender_id, state)
        if handler_name in text_sender_handlers:
            return fn(text_normalized, sender_id, state)
        return fn(text_normalized, state)

    def _process_prompt_and_branch(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        prompt_stage_key = "_flow_prompt_stage"

        # Primeira vez que entra no nó: apenas envia prompt e aguarda a próxima mensagem.
        if state.get(prompt_stage_key) != node.id:
            state[prompt_stage_key] = node.id
            return ((node.prompt or ""), state, False)

        # Segunda vez (usuário respondeu): avaliar transições e avançar stage.
        transition = self._choose_transition(node=node, text_raw=text_raw, text_normalized=text_normalized)
        if transition:
            self._maybe_execute_transition_actions(transition=transition, sender_id=sender_id, state=state)
            new_state = self._apply_transition_effects(state=state, transition=transition, sender_id=sender_id)

            # Limpa o marcador de prompt ANTES de definir o novo stage
            new_state.pop(prompt_stage_key, None)

            # Permite encerrar a conversa sem forçar stage (ex.: usuário não quer agendar)
            if getattr(transition, "to", None):
                new_state["stage"] = transition.to

            # Se o destino for o mesmo nó, não limpamos o marcador (permitindo retry)
            if transition.to == node.id:
                new_state[prompt_stage_key] = node.id

            # Continua o loop para processar o próximo stage na mesma requisição.
            return (
                self._transition_message_override(transition, sender_id=sender_id, state=new_state) or "",
                new_state,
                self._transition_continue_loop(transition, default=True),
            )

            # retry no mesmo nó
            return (
                self._transition_message_override(transition, sender_id=sender_id, state=new_state) or (node.prompt or ""),
                new_state,
                self._transition_continue_loop(transition, default=False),
            )

        # Sem transição válida: mantém stage e reenvia prompt (fallback conservador)
        return ((node.prompt or ""), state, False)

    def _choose_transition(self, *, node: FlowNodeV1, text_raw: str, text_normalized: str) -> Optional[Any]:
        default_transition: Optional[Any] = None
        for t in (node.transitions or []):
            when = t.when or {}

            # Se não há condição explícita, tratamos como default.
            # Isso evita ficar preso em nós de prompt quando a UI cria transições
            # sem configurar `when`.
            if not when and default_transition is None:
                default_transition = t
                continue

            if when.get("default") is True:
                default_transition = t
                continue

            yes_no = when.get("yes_no")
            if yes_no in {"yes", "no"}:
                if detect.detect_yes_no(text_raw) == yes_no:
                    return t

            if when.get("schedule_intent") is True:
                if detect.detect_schedule_intent(text_raw):
                    return t

            equals_any = when.get("equals_any")
            if isinstance(equals_any, list):
                v = (text_normalized or "").strip()
                if any(v == str(x).strip().lower() for x in equals_any):
                    return t

            contains_any = when.get("contains_any")
            if isinstance(contains_any, list):
                v = (text_normalized or "").strip()
                if any(str(x).strip().lower() in v for x in contains_any):
                    return t

        return default_transition

    def _process_capture_phone(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        phone_field = config.get("phone_field")
        if not isinstance(phone_field, str) or not phone_field.strip():
            phone_field = "visit_phone"

        valid_to = config.get("valid_to")
        if not isinstance(valid_to, str) or not valid_to.strip():
            valid_to = "awaiting_visit_date"

        confirm_existing_to = config.get("confirm_existing_to")
        if not isinstance(confirm_existing_to, str) or not confirm_existing_to.strip():
            confirm_existing_to = valid_to

        # 1) Atalho: usuário confirmou ("sim/ok/correto") para manter telefone atual
        positive_words = {
            "sim",
            "correto",
            "ok",
            "confirmo",
            "esse mesmo",
            "está correto",
            "esta correto",
        }
        tl = (text_normalized or "").strip()
        if any(w in tl for w in positive_words):
            current_phone = state.get(phone_field)
            if isinstance(current_phone, str) and current_phone.strip():
                state["stage"] = confirm_existing_to
                return (fmt.format_request_visit_date(), state, False)

        # 2) Validar entrada como telefone
        is_valid, formatted_phone = VisitService.validate_phone(text_raw)
        if is_valid:
            state[phone_field] = formatted_phone
            state["stage"] = valid_to
            return (fmt.format_request_visit_date(), state, False)

        # 3) Inválido
        # Mantém stage atual (awaiting_phone_input) e retorna erro
        return (fmt.format_invalid_phone(), state, False)

    def _process_capture_date(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        valid_to = config.get("valid_to")
        if not isinstance(valid_to, str) or not valid_to.strip():
            valid_to = "awaiting_visit_time"

        parsed_date = VisitService.parse_date_input(text_raw)
        if parsed_date:
            state["visit_date"] = parsed_date.isoformat()
            state["visit_date_display"] = parsed_date.strftime("%d/%m/%Y")
            state["stage"] = valid_to
            return (fmt.format_request_visit_time(), state, False)

        return (fmt.format_invalid_date(), state, False)

    def _process_capture_time(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        config = node.config or {}
        if not isinstance(config, dict):
            config = {}

        # Parse da data base
        visit_date_str = state.get("visit_date")
        if not isinstance(visit_date_str, str) or not visit_date_str.strip():
            msg = "Erro: data não encontrada. Vamos recomeçar o agendamento."
            state["stage"] = "awaiting_visit_date"
            return (msg, state, False)

        try:
            visit_date = datetime.fromisoformat(visit_date_str)
        except Exception:
            msg = "Erro: data inválida. Vamos recomeçar o agendamento."
            state["stage"] = "awaiting_visit_date"
            return (msg, state, False)

        parsed_time = VisitService.parse_time_input(text_raw, visit_date)
        if not parsed_time:
            return (fmt.format_invalid_time(), state, False)

        # Guardrail: impedir agendamento no passado
        if parsed_time < datetime.now():
            return (fmt.format_past_time_error(parsed_time.strftime("%H:%M")), state, False)

        user_name = state.get("user_name", "Cliente")
        phone_display = state.get("visit_phone", sender_id.split("@")[0] if "@" in sender_id else sender_id)
        phone_full = sender_id

        property_id = state.get("directed_property_id") or state.get("interested_property_id")
        property_code = state.get("directed_property_code", "")
        if not property_id:
            msg = "Erro: não consegui identificar o imóvel. Vamos recomeçar o agendamento."
            state["stage"] = "awaiting_visit_date"
            return (msg, state, False)

        # Buscar ou criar lead por telefone (compatibilidade: com e sem @c.us)
        lead = (
            self.db.query(Lead)
            .filter((Lead.phone == phone_full) | (Lead.phone == phone_display))
            .first()
        )

        property_data: Dict[str, Any] = {}
        try:
            prop = self.db.query(Property).filter(Property.id == property_id).first()
            if prop:
                property_data = {
                    "finalidade": prop.purpose.value if getattr(prop, "purpose", None) else None,
                    "tipo": prop.type.value if getattr(prop, "type", None) else None,
                    "cidade": getattr(prop, "address_city", None),
                    "estado": getattr(prop, "address_state", None),
                    "bairro": getattr(prop, "address_neighborhood", None),
                    "dormitorios": getattr(prop, "bedrooms", None),
                    "preco_min": getattr(prop, "price", None),
                    "preco_max": getattr(prop, "price", None),
                    "ref_code": getattr(prop, "ref_code", None),
                }
        except Exception:
            property_data = {}

        pref_bedrooms = state.get("bedrooms")
        try:
            pref_bedrooms = int(pref_bedrooms) if pref_bedrooms is not None else None
        except Exception:
            pref_bedrooms = None

        lead_updates = {
            "name": user_name,
            "status": "agendamento_pendente",
            "property_interest_id": property_id,
            "external_property_id": property_data.get("ref_code"),
            "finalidade": state.get("purpose") or property_data.get("finalidade"),
            "tipo": state.get("type") or property_data.get("tipo"),
            "cidade": state.get("city") or property_data.get("cidade"),
            "estado": state.get("state") or property_data.get("estado"),
            "bairro": state.get("neighborhood") or property_data.get("bairro"),
            "dormitorios": (pref_bedrooms if pref_bedrooms is not None else property_data.get("dormitorios")),
            "preco_min": state.get("price_min") or property_data.get("preco_min"),
            "preco_max": state.get("price_max") or property_data.get("preco_max"),
            "last_inbound_at": datetime.utcnow(),
        }

        if not lead:
            lead_data = {
                "tenant_id": state.get("tenant_id"),
                "nome": user_name,
                "telefone": phone_full,
                "origem": "whatsapp",
                "status": "agendamento_pendente",
                "property_interest_id": property_id,
            }
            lead = LeadService.create_lead(self.db, lead_data)

        for key, value in lead_updates.items():
            if key == "name" or value is not None:
                setattr(lead, key, value)
        self.db.commit()

        visit_id = VisitService.create_visit(
            db=self.db,
            lead_id=int(getattr(lead, "id")),
            property_id=int(property_id),
            phone=phone_full,
            visit_datetime=parsed_time,
            notes=f"Agendamento via WhatsApp - Imóvel #{property_code}",
        )

        try:
            NotificationService.notify_visit_requested(self.db, int(visit_id))
        except Exception:
            pass

        date_str = state.get("visit_date_display") or parsed_time.strftime("%d/%m/%Y")
        time_str = parsed_time.strftime("%H:%M")
        msg = fmt.format_visit_scheduled(user_name, date_str, time_str, str(property_code or ""))
        return (msg, {}, False)

    def _process_capture_property_type(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        tl = (text_normalized or "").strip()
        user_name = state.get("user_name", "")

        prop_type: Optional[str] = None
        if tl in ["1", "1️⃣", "um", "primeiro"]:
            prop_type = "house"
        elif tl in ["2", "2️⃣", "dois", "segundo"]:
            prop_type = "apartment"
        elif tl in ["3", "3️⃣", "três", "tres", "terceiro"]:
            prop_type = "commercial"
        elif tl in ["4", "4️⃣", "quatro", "quarto"]:
            prop_type = "land"
        else:
            prop_type = detect.detect_property_type(text_raw)

        if prop_type in {"house", "apartment", "commercial", "land"}:
            state["type"] = prop_type
            state["stage"] = "awaiting_price_min"
            purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
            type_names = {
                "house": "casa",
                "apartment": "apartamento",
                "commercial": "comercial",
                "land": "terreno",
            }
            type_display = type_names.get(prop_type, prop_type)
            msg = (
                f"Entendido{', ' + user_name if user_name else ''}! Você quer {type_display}.\n\n"
                f"Qual o valor *mínimo* que você considera para {purpose_txt}?\n\n"
                "💡 Exemplos: '200000', '200 mil', '200k'"
            )
            return (msg, state, False)

        name_prefix = f"{user_name}, " if user_name else ""
        msg = (
            f"{name_prefix}não entendi o tipo. Por favor, escolha uma opção:\n\n"
            "1️⃣ *Casa*\n"
            "2️⃣ *Apartamento*\n"
            "3️⃣ *Comercial*\n"
            "4️⃣ *Terreno*\n\n"
            "Digite o número ou o nome."
        )
        return (msg, state, False)

    def _process_capture_price_min(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        # PRIORIDADE: extract_price (regex/extenso)
        raw_price = detect.extract_price(text_raw)
        if raw_price is None:
            ent = (state.get("llm_entities") or {})
            raw_price = ent.get("preco_min")

        purpose = state.get("purpose", "sale")
        validated = validate_price(raw_price, purpose)
        if validated is not None:
            state["price_min"] = validated

            # Se já tem cidade (refinamento), buscar direto SEM mensagem
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)

            state["stage"] = "awaiting_price_max"
            purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
            msg = f"Perfeito! E qual o valor *máximo* para {purpose_txt}?"
            return (msg, state, False)

        purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
        range_txt = "R$ 300 a R$ 50.000" if purpose == "rent" else "R$ 50.000 a R$ 10.000.000"
        msg = (
            f"Não consegui identificar o valor. Por favor, informe o valor mínimo para {purpose_txt}.\n\n"
            f"💡 Faixa válida: {range_txt}\n"
            "💡 Exemplos: '200000', '200 mil', '200k'"
        )
        return (msg, state, False)

    def _process_capture_price_max(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        raw_price = detect.extract_price(text_raw)
        if raw_price is None:
            ent = (state.get("llm_entities") or {})
            raw_price = ent.get("preco_max")

        purpose = state.get("purpose", "sale")
        validated = validate_price(raw_price, purpose)
        if validated is not None:
            state["price_max"] = validated

            # Se já tem cidade (refinamento), buscar direto SEM mensagem
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)

            state["stage"] = "awaiting_bedrooms"
            msg = "Ótimo! Quantos quartos você precisa?\n\n💡 Exemplos: '2', '3 quartos', 'tanto faz'"
            return (msg, state, False)

        purpose_txt = "aluguel" if state.get("purpose") == "rent" else "compra"
        range_txt = "R$ 300 a R$ 50.000" if purpose == "rent" else "R$ 50.000 a R$ 10.000.000"
        msg = (
            f"Não consegui identificar o valor. Por favor, informe o valor máximo para {purpose_txt}.\n\n"
            f"💡 Faixa válida: {range_txt}\n"
            "💡 Exemplos: '500000', '500 mil', '500k'"
        )
        return (msg, state, False)

    def _process_capture_bedrooms(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        ent = (state.get("llm_entities") or {})
        bedrooms_raw = ent.get("dormitorios")
        if bedrooms_raw is None:
            bedrooms_raw = detect.extract_bedrooms(text_raw)

        bedrooms = validate_bedrooms(bedrooms_raw)
        tl = (text_normalized or "").strip()
        is_any = tl in {"tanto faz", "qualquer", "qualquer um", "não importa"}

        if bedrooms is not None or is_any:
            state["bedrooms"] = bedrooms

            # Se já tem cidade (refinamento), buscar direto SEM mensagem
            if state.get("city"):
                state["stage"] = "searching"
                return ("", state, True)

            state["stage"] = "awaiting_city"
            msg = "Perfeito! Em qual cidade você está procurando?"
            return (msg, state, False)

        msg = (
            "Não consegui identificar a quantidade de quartos. Por favor, responda:\n\n"
            "1️⃣ *1 quarto*\n"
            "2️⃣ *2 quartos*\n"
            "3️⃣ *3 quartos*\n"
            "4️⃣ *4 quartos*\n"
            "5️⃣ *Tanto faz*"
        )
        return (msg, state, False)

    def _process_capture_city(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        ent = (state.get("llm_entities") or {})
        cidade_raw = ent.get("cidade") or text_raw
        cidade = validate_city(cidade_raw)

        user_name = state.get("user_name", "")
        if cidade:
            state["city"] = cidade
            state["stage"] = "awaiting_neighborhood"
            msg = f"Ótimo{', ' + user_name if user_name else ''}! Você tem preferência por algum *bairro* em {cidade}? (ou 'não')"
            return (msg, state, False)

        name_prefix = f"{user_name}, " if user_name else ""
        msg = (
            f"{name_prefix}não consegui identificar a cidade. Por favor, informe uma cidade válida.\n\n"
            "💡 Exemplos: 'São Paulo', 'Mogi das Cruzes', 'Santos'"
        )
        return (msg, state, False)

    def _process_capture_neighborhood(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        if detect.is_skip_neighborhood(text_raw):
            state["neighborhood"] = None
        else:
            state["neighborhood"] = text_raw.strip().title()

        state["stage"] = "searching"
        return ("", state, True)

    def _process_execute_search(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        # Corrigir price_min > price_max (erro comum de interpretação)
        price_min = state.get("price_min")
        price_max = state.get("price_max")
        if price_min is not None and price_max is not None:
            try:
                if float(price_min) > float(price_max):
                    state["price_min"], state["price_max"] = price_max, price_min
                    price_min, price_max = state["price_min"], state["price_max"]
            except Exception:
                pass

        stmt = select(Property).where(Property.is_active == True)  # noqa: E712

        if state.get("purpose"):
            stmt = stmt.where(Property.purpose == PropertyPurpose(state["purpose"]))
        if state.get("type"):
            stmt = stmt.where(Property.type == PropertyType(state["type"]))
        if state.get("city"):
            stmt = stmt.where(Property.address_city.ilike(f"%{state['city']}%"))
        if state.get("neighborhood"):
            stmt = stmt.where(Property.address_neighborhood.ilike(f"%{state['neighborhood']}%"))
        if state.get("price_min") is not None:
            try:
                stmt = stmt.where(Property.price >= float(state["price_min"]))
            except Exception:
                pass
        if state.get("price_max") is not None:
            try:
                stmt = stmt.where(Property.price <= float(state["price_max"]))
            except Exception:
                pass
        if state.get("bedrooms") is not None:
            try:
                stmt = stmt.where(Property.bedrooms == int(state["bedrooms"]))
            except Exception:
                pass

        stmt = stmt.limit(20)
        results = self.db.execute(stmt).scalars().all()
        if not results:
            LeadService.create_unqualified_lead(
                self.db,
                sender_id,
                state,
                state.get("lgpd_consent", False),
            )
            user_name = state.get("user_name", "")
            msg = fmt.format_no_results_message(state.get("city", "sua cidade"), user_name)
            state["stage"] = "awaiting_refinement"
            return (msg, state, False)

        state["search_results"] = [r.id for r in results]
        state["current_property_index"] = 0
        state["stage"] = "showing_property"
        return ("", state, True)

    def _process_show_property_card(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        results = state.get("search_results", [])
        idx = state.get("current_property_index", 0)
        try:
            idx_int = int(idx)
        except Exception:
            idx_int = 0

        if not isinstance(results, list):
            results = []

        user_name = state.get("user_name", "")

        # Se não há mais imóveis
        if idx_int >= len(results):
            msg = fmt.format_no_more_properties(user_name)
            state["stage"] = "awaiting_refinement"
            return (msg, state, False)

        prop_id = results[idx_int]
        try:
            prop_id_int = int(prop_id)
        except Exception:
            prop_id_int = None

        prop = self.db.get(Property, prop_id_int) if prop_id_int is not None else None
        if not prop:
            # Imóvel não encontrado, pular para próximo
            state["current_property_index"] = idx_int + 1
            return ("", state, True)

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

        shown_list = state.get("shown_properties") or []
        if not isinstance(shown_list, list):
            shown_list = []
        shown_list.append(
            {
                "id": prop.id,
                "ref_code": prop.ref_code,
                "external_id": prop.external_id,
            }
        )
        state["shown_properties"] = shown_list

        total = len(results)
        current = idx_int + 1
        counter = f"\n\n📊 Imóvel {current} de {total}" if total > 1 else ""

        msg = fmt.format_property_card(prop_details, state.get("purpose", "rent"), user_name) + counter
        state["stage"] = "awaiting_property_feedback"
        return (msg, state, False)

    def _process_property_feedback_decision(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        # PRIORIDADE 1: Detectar refinamento (reusar rotina do legacy)
        try:
            refinement_fn = getattr(self._handler, "_detect_refinement_intent", None)
            if refinement_fn is not None:
                refinement_result = refinement_fn(text_raw, state)
                if refinement_result:
                    return refinement_result
        except Exception:
            pass

        # PRIORIDADE 1.5: Encerrar por "Não encontrei imóvel"
        if detect.detect_no_match(text_raw):
            try:
                prefs = dict(state)
                LeadService.create_unqualified_lead(
                    self.db,
                    sender_id,
                    prefs,
                    state.get("lgpd_consent", False),
                )
            except Exception:
                pass
            user_name = state.get("user_name", "")
            msg = fmt.format_no_match_final(user_name)
            return (msg, {}, False)

        # PRIORIDADE 2: Interesse no imóvel -> mostrar detalhes
        if detect.detect_interest(text_raw):
            results = state.get("search_results", [])
            idx = state.get("current_property_index", 0)
            try:
                idx_int = int(idx)
            except Exception:
                idx_int = 0

            if not isinstance(results, list) or idx_int >= len(results):
                state["stage"] = "awaiting_refinement"
                return (fmt.format_no_more_properties(state.get("user_name", "")), state, False)

            prop_id = results[idx_int]
            try:
                prop_id_int = int(prop_id)
            except Exception:
                prop_id_int = None

            prop = self.db.get(Property, prop_id_int) if prop_id_int is not None else None
            if not prop:
                msg = "Desculpe, houve um erro. Vamos para o próximo imóvel."
                state["current_property_index"] = idx_int + 1
                state["stage"] = "showing_property"
                return (msg, state, True)

            images = (
                self.db.execute(
                    select(PropertyImage)
                    .where(PropertyImage.property_id == int(prop.id))
                    .order_by(PropertyImage.sort_order.asc())
                    .limit(3)
                )
                .scalars()
                .all()
            )
            image_urls = [img.url for img in images] if images else []

            prop_details = {
                "descricao": prop.description,
                "dormitorios": prop.bedrooms,
                "banheiros": prop.bathrooms,
                "vagas": prop.parking_spots,
                "area_total": prop.area_total,
                "images": image_urls,
            }

            user_name = state.get("user_name", "")
            msg = fmt.format_property_details(prop_details, user_name)
            state["interested_property_id"] = int(prop.id)
            state["property_detail_images"] = image_urls

            detailed_list = state.get("detailed_properties") or []
            if not isinstance(detailed_list, list):
                detailed_list = []
            detailed_list.append(
                {
                    "id": int(prop.id),
                    "ref_code": getattr(prop, "ref_code", None),
                    "external_id": getattr(prop, "external_id", None),
                }
            )
            state["detailed_properties"] = detailed_list

            state["stage"] = "awaiting_visit_decision"
            return (msg, state, False)

        # PRIORIDADE 3: Próximo imóvel
        if detect.detect_next_property(text_raw):
            try:
                state["current_property_index"] = int(state.get("current_property_index", 0) or 0) + 1
            except Exception:
                state["current_property_index"] = 1
            state["stage"] = "showing_property"
            return ("", state, True)

        msg = (
            "Gostou deste imóvel? Digite *'sim'* para mais detalhes, *'próximo'* para ver outra opção, "
            "*'ajustar critérios'* para refinar a busca ou *'não encontrei imóvel'* para encerrar."
        )
        return (msg, state, False)

    def _process_refinement_decision(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        # Reuso seguro: a lógica de refinamento ainda é complexa e específica do domínio.
        # Mantemos o comportamento atual delegando para o handler legacy.
        msg, new_state, continue_loop = self._call_legacy_handler(
            handler_name="refinement",
            sender_id=sender_id,
            text_raw=text_raw,
            text_normalized=text_normalized,
            state=state,
        )
        return (msg, new_state, continue_loop)

    def _process_capture_purpose(
        self,
        *,
        node: FlowNodeV1,
        sender_id: str,
        text_raw: str,
        text_normalized: str,
        state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        tl = (text_normalized or "").strip()
        user_name = state.get("user_name", "")

        purpose: Optional[str] = None
        if tl in ["1", "1️⃣", "um", "primeiro"]:
            purpose = "sale"
        elif tl in ["2", "2️⃣", "dois", "segundo"]:
            purpose = "rent"
        else:
            purpose = detect.detect_purpose(text_raw)

        if purpose in {"sale", "rent"}:
            state["purpose"] = purpose
            state["stage"] = "awaiting_type"
            purpose_txt = "comprar" if purpose == "sale" else "alugar"
            msg = (
                f"Perfeito{', ' + user_name if user_name else ''}! Você quer {purpose_txt}.\n\n"
                "Agora me diga, que tipo de imóvel você prefere:\n\n"
                "1️⃣ *Casa*\n"
                "2️⃣ *Apartamento*\n"
                "3️⃣ *Comercial*\n"
                "4️⃣ *Terreno*\n\n"
                "Digite o número ou o nome do tipo."
            )
            return (msg, state, False)

        name_prefix = f"{user_name}, " if user_name else ""
        msg = (
            f"{name_prefix}não entendi. Por favor, escolha uma opção:\n\n"
            "1️⃣ *Comprar* um imóvel\n"
            "2️⃣ *Alugar* um imóvel\n\n"
            "Digite 1 ou 2, ou escreva 'comprar' ou 'alugar'."
        )
        return (msg, state, False)

    def _apply_transition_effects(self, *, state: Dict[str, Any], transition: Any, sender_id: str) -> Dict[str, Any]:
        effects = getattr(transition, "effects", None) or {}
        if not isinstance(effects, dict):
            return state

        out = state

        if effects.get("clear_state") is True:
            out = {}
            return out

        keep = effects.get("reset_state_keep")
        if isinstance(keep, list):
            out = {k: out.get(k) for k in keep if k in out}

        patch = effects.get("set")
        if isinstance(patch, dict):
            out.update(patch)

        if effects.get("set_visit_phone_from_sender") is True:
            phone = sender_id.split("@")[0] if "@" in sender_id else sender_id
            out["visit_phone"] = phone

        return out

    def _transition_message_override(self, transition: Any, *, sender_id: str, state: Dict[str, Any]) -> Optional[str]:
        effects = getattr(transition, "effects", None) or {}
        if not isinstance(effects, dict):
            return None

        msg = effects.get("message")
        if isinstance(msg, str):
            return msg

        template = effects.get("message_template")
        if template == "confirm_phone":
            phone = state.get("visit_phone")
            if isinstance(phone, str) and phone.strip():
                return fmt.format_confirm_phone(phone)

        if template == "request_visit_date":
            return fmt.format_request_visit_date()

        if template == "request_alternative_phone":
            return fmt.format_request_alternative_phone()

        return None

    def _maybe_execute_transition_actions(self, *, transition: Any, sender_id: str, state: Dict[str, Any]) -> None:
        effects = getattr(transition, "effects", None) or {}
        if not isinstance(effects, dict):
            return
        if effects.get("mark_qualified") is True:
            try:
                LeadService.mark_qualified(self.db, sender_id, state)
            except Exception:
                pass

    def _transition_continue_loop(self, transition: Any, *, default: bool) -> bool:
        effects = getattr(transition, "effects", None) or {}
        if isinstance(effects, dict) and isinstance(effects.get("continue_loop"), bool):
            return bool(effects["continue_loop"])
        return bool(default)

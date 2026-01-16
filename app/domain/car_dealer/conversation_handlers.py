from __future__ import annotations

import re
from typing import Any, Dict, Tuple, List

from sqlalchemy.orm import Session

from app.domain.catalog.models import CatalogItem, CatalogItemType


class CarDealerConversationHandler:
    def __init__(self, db: Session):
        self.db = db

    def handle_start(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        # Entry stage used by FlowEngine handler nodes.
        state.setdefault("car_dealer", {})
        state.setdefault("stage", "start")
        return ("", state, False)

    def handle_set_intent_buy(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        state["car_dealer"]["intent"] = "buy"
        state["stage"] = "buy_capture_make_model"
        return ("", state, True)

    def handle_set_intent_sell(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        state["car_dealer"]["intent"] = "sell"
        state["stage"] = "sell_capture_vehicle"
        return ("", state, True)

    def handle_set_intent_finance(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        state["car_dealer"]["intent"] = "finance"
        state["stage"] = "finance_capture_vehicle"
        return ("", state, True)

    def handle_buy_capture_make_model(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        raw = (text or "").strip()
        if not raw or len(raw) < 2:
            return ("Qual carro você procura? Ex: *Onix 2020*, *Corolla*, *HB20*.", state, False)

        # Best-effort extraction: take first 2-4 tokens, ignore filler.
        tokens = [t for t in re.split(r"\s+", raw) if t]
        tokens = [t for t in tokens if t.lower() not in {"quero", "um", "uma", "carro", "veiculo", "veículo"}]
        guess = " ".join(tokens[:4]).strip()
        if guess:
            state["car_dealer"]["query"] = guess
        state["stage"] = "buy_capture_budget"
        return ("Perfeito. Qual seu orçamento máximo? Ex: *70000* ou *70 mil*.", state, False)

    def handle_buy_capture_budget(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        raw = (text or "").lower()
        raw = raw.replace("r$", " ").replace(".", " ").replace(",", " ")
        m = re.search(r"(\d{2,9})", raw)
        if not m:
            return ("Não entendi o orçamento. Me diga um valor (ex: *70000* ou *70 mil*).", state, False)

        v = int(m.group(1))
        # Heuristic: '70' probably means '70 mil'
        if v < 1000:
            v = v * 1000
        state["car_dealer"]["budget_max"] = int(v)
        state["stage"] = "buy_execute_search"
        return ("", state, True)

    def handle_buy_execute_search(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        tenant_id = int(state.get("tenant_id") or 0)
        if not tenant_id:
            return ("Não consegui identificar o tenant para buscar veículos.", state, False)

        query = str((state.get("car_dealer") or {}).get("query") or "").strip().lower()
        budget_max = (state.get("car_dealer") or {}).get("budget_max")
        try:
            budget_max_int = int(budget_max) if budget_max is not None else None
        except Exception:
            budget_max_int = None

        items = self._search_vehicles(tenant_id=tenant_id, query=query, budget_max=budget_max_int, limit=3)
        if not items:
            state.setdefault("car_dealer", {})
            state["car_dealer"]["last_results"] = []
            state["stage"] = "handoff"
            return (
                "No momento não encontrei veículos com esse perfil. Posso te colocar com um atendente para te ajudar?",
                state,
                False,
            )

        state.setdefault("car_dealer", {})
        state["car_dealer"]["last_results"] = [int(x["id"]) for x in items]
        state["stage"] = "buy_select_vehicle"

        lines: List[str] = ["Encontrei essas opções:"]
        for idx, it in enumerate(items, start=1):
            price = it.get("price")
            price_str = f"R$ {price:,.0f}".replace(",", ".") if isinstance(price, (int, float)) else "Consulte"
            year = it.get("year")
            km = it.get("km")
            extras: List[str] = []
            if year is not None:
                extras.append(str(year))
            if km is not None:
                extras.append(f"{int(km):,} km".replace(",", "."))
            extra_str = " • ".join(extras)
            lines.append(f"{idx}) {it.get('title') or 'Veículo'} — {price_str}" + (f" ({extra_str})" if extra_str else ""))

        lines.append("\nResponda com *1*, *2* ou *3* para eu te passar mais detalhes, ou escreva *refinar* para ajustar a busca.")
        return ("\n".join(lines), state, False)

    def handle_buy_select_vehicle(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        raw = (text or "").strip().lower()
        if "refin" in raw:
            state["stage"] = "buy_capture_make_model"
            return ("Beleza. Me diga novamente qual carro você procura.", state, False)

        m = re.search(r"\b([1-3])\b", raw)
        if not m:
            return ("Me diga *1*, *2* ou *3* (ou *refinar*).", state, False)

        idx = int(m.group(1)) - 1
        ids = list((state.get("car_dealer") or {}).get("last_results") or [])
        if idx < 0 or idx >= len(ids):
            return ("Opção inválida. Me diga *1*, *2* ou *3*.", state, False)

        state.setdefault("car_dealer", {})
        state["car_dealer"]["selected_vehicle_id"] = int(ids[idx])
        state["stage"] = "handoff"
        return ("Ótimo. Para eu te colocar com um atendente e agilizar, me confirme seu telefone com DDD.", state, False)

    def handle_sell_capture_vehicle(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        raw = (text or "").strip()
        if not raw or len(raw) < 3:
            return ("Qual veículo você quer vender? Ex: *Onix 2019*, *Corolla 2018*.", state, False)
        state["car_dealer"]["sell_vehicle"] = raw
        state["stage"] = "handoff"
        return ("Perfeito. Me confirme seu telefone com DDD para um atendente avaliar.", state, False)

    def handle_finance_capture_vehicle(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        raw = (text or "").strip()
        if not raw or len(raw) < 3:
            return ("Qual veículo você quer financiar? Ex: *Onix 2020*, *Corolla*.", state, False)
        state["car_dealer"]["finance_vehicle"] = raw
        state["stage"] = "handoff"
        return ("Perfeito. Me confirme seu telefone com DDD para um atendente te ajudar.", state, False)

    def handle_handoff(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state.setdefault("car_dealer", {})
        phone = self._extract_phone_from_text(text)
        if not phone:
            return ("Me passe seu telefone com DDD (ex: 31999990000).", state, False)
        state["car_dealer"]["phone"] = phone
        state["car_dealer"]["completed"] = True
        # Reset to start for the next inbound message. (FlowEngine does not execute 'end' node types.)
        state["stage"] = "start"
        return ("Obrigado! Já encaminhei para um atendente. Em instantes falamos com você.", state, False)

    def _extract_phone_from_text(self, text: str) -> str | None:
        raw = re.sub(r"\D", "", (text or ""))
        if len(raw) < 10:
            return None
        if len(raw) > 13:
            raw = raw[-13:]
        return raw

    def _search_vehicles(self, *, tenant_id: int, query: str, budget_max: int | None, limit: int) -> list[dict[str, Any]]:
        q = (
            self.db.query(CatalogItem)
            .join(CatalogItemType, CatalogItemType.id == CatalogItem.item_type_id)
            .filter(
                CatalogItem.tenant_id == int(tenant_id),
                CatalogItem.is_active == True,  # noqa: E712
                CatalogItemType.key == "vehicle",
            )
            .order_by(CatalogItem.id.desc())
            .limit(80)
        )
        rows = q.all()

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip().lower())

        query_n = norm(query)
        out: list[dict[str, Any]] = []
        for r in rows:
            title = str(getattr(r, "title", "") or "")
            attrs = dict(getattr(r, "attributes", {}) or {})
            make = str(attrs.get("make") or "")
            model = str(attrs.get("model") or "")
            hay = norm(" ".join([title, make, model]))

            if query_n and query_n not in hay:
                continue

            price = attrs.get("price")
            try:
                price_n = float(price) if price is not None else None
            except Exception:
                price_n = None
            if budget_max is not None and price_n is not None and price_n > float(budget_max):
                continue

            out.append(
                {
                    "id": int(r.id),
                    "title": title,
                    "price": price_n,
                    "year": attrs.get("year"),
                    "km": attrs.get("km"),
                }
            )

            if len(out) >= int(limit):
                break

        return out

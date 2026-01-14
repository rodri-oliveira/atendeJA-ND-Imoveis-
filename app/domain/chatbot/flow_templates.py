from __future__ import annotations

from typing import Any, Dict, List

from app.domain.realestate.default_flow import get_default_flow_nodes


def list_available_templates() -> List[Dict[str, str]]:
    return [
        {"domain": "real_estate", "template": "default"},
        {"domain": "car_dealer", "template": "default"},
    ]


def get_flow_template_definition(*, domain: str, template: str) -> Dict[str, Any]:
    d = (domain or "").strip() or "real_estate"
    t = (template or "").strip() or "default"

    if d == "real_estate" and t == "default":
        return {
            "version": 1,
            "start": "start",
            "nodes": get_default_flow_nodes(),
        }

    if d == "car_dealer" and t == "default":
        return {
            "version": 1,
            "start": "start",
            "nodes": [
                {
                    "id": "start",
                    "type": "prompt_and_branch",
                    "prompt": "🚗 *Atendimento Auto*\n\nComo posso te ajudar hoje?",
                    "transitions": [],
                },
            ],
        }

    raise ValueError("template_not_found")

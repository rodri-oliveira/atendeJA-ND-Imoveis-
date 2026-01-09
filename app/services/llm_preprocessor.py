from __future__ import annotations

import os
from typing import Any, Dict

from app.core.config import settings


async def enrich_state_with_llm(*, sender_id: str, text_raw: str, state: Dict[str, Any], log) -> Dict[str, Any]:
    env = (settings.APP_ENV or "").lower()
    is_pytest = os.getenv("PYTEST_CURRENT_TEST") is not None
    if not text_raw.strip() or env == "test" or is_pytest:
        return state

    try:
        log.info(
            "llm_extraction_start",
            sender_id=sender_id,
            user_input=text_raw,
            input_length=len(text_raw),
            current_stage=state.get("stage", "start"),
        )

        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        llm_result = await llm.extract_intent_and_entities(text_raw)

        log.info(
            "llm_extraction_raw",
            sender_id=sender_id,
            raw_intent=(llm_result.get("intent") if isinstance(llm_result, dict) else None),
            raw_entities=(llm_result.get("entities", {}) if isinstance(llm_result, dict) else {}),
        )

        if isinstance(llm_result, dict):
            from app.domain.realestate.validation_utils import sanitize_llm_result

            current_stage = state.get("stage", "start")
            sanitized_result = sanitize_llm_result(llm_result, text_raw, current_stage)

            if llm_result != sanitized_result:
                log.warning(
                    "llm_result_changed_by_sanitization",
                    sender_id=sender_id,
                    original_intent=llm_result.get("intent"),
                    sanitized_intent=sanitized_result.get("intent"),
                    original_entities=llm_result.get("entities", {}),
                    sanitized_entities=sanitized_result.get("entities", {}),
                )
            else:
                log.debug("llm_result_unchanged_by_sanitization", sender_id=sender_id)

            state["llm_intent"] = sanitized_result.get("intent")
            state["llm_entities"] = sanitized_result.get("entities") or {}
            state["llm_original"] = llm_result

            log.info(
                "llm_extraction_final",
                sender_id=sender_id,
                final_intent=state.get("llm_intent"),
                final_entities=state.get("llm_entities"),
            )

    except Exception as e:  # noqa: BLE001
        log.error("llm_extraction_failed", sender_id=sender_id, error=str(e), user_input=text_raw)

    return state

from __future__ import annotations

from typing import Any, Dict, Optional


def normalize_state(*, state: Optional[Dict[str, Any]], sender_id: str, tenant_id: int, default_stage: str = "start") -> Dict[str, Any]:
    out = dict(state or {})
    out.setdefault("sender_id", sender_id)
    out.setdefault("tenant_id", int(tenant_id))
    out.setdefault("stage", default_stage)
    return out

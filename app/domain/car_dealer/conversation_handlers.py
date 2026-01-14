from __future__ import annotations

from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session


class CarDealerConversationHandler:
    def __init__(self, db: Session):
        self.db = db

    def handle_start(self, text: str, state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
        state["stage"] = "awaiting_lgpd_consent"
        return ("🚗 Car Dealer handler", state, False)

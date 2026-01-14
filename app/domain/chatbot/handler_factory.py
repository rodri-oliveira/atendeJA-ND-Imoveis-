from __future__ import annotations

from sqlalchemy.orm import Session


def get_conversation_handler_for_domain(*, domain: str, db: Session):
    d = (domain or "").strip() or "real_estate"

    if d == "car_dealer":
        from app.domain.car_dealer.conversation_handlers import CarDealerConversationHandler

        return CarDealerConversationHandler(db)

    # default
    from app.domain.realestate.conversation_handlers import ConversationHandler

    return ConversationHandler(db)

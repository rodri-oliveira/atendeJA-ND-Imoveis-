from __future__ import annotations

from typing import Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.realestate.chatbot_flow_schema import ChatbotFlowDefinitionV1
from app.domain.realestate.models import ChatbotFlow


class ChatbotFlowService:
    def __init__(self, db: Session):
        self.db = db

    def get_published_flow(self, tenant_id: int, domain: str = "real_estate") -> Optional[ChatbotFlow]:
        stmt = (
            select(ChatbotFlow)
            .where(
                ChatbotFlow.tenant_id == int(tenant_id),
                ChatbotFlow.domain == domain,
                ChatbotFlow.is_published == True,  # noqa: E712
            )
            .order_by(ChatbotFlow.published_version.desc(), ChatbotFlow.updated_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def validate_definition(self, flow_definition: dict) -> ChatbotFlowDefinitionV1:
        try:
            return ChatbotFlowDefinitionV1.model_validate(flow_definition)
        except ValidationError as e:
            raise ValueError(f"invalid_flow_definition: {e}")

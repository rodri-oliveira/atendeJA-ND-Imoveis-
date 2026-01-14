from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class FlowTransitionV1(BaseModel):
    to: str
    when: Optional[Dict[str, Any]] = None
    effects: Optional[Dict[str, Any]] = None


class FlowNodeV1(BaseModel):
    id: str
    type: Literal[
        "static_message",
        "end",
        "handler",
        "prompt_and_branch",
        "capture_phone",
        "capture_date",
        "capture_time",
        "capture_purpose",
        "capture_property_type",
        "capture_price_min",
        "capture_price_max",
        "capture_bedrooms",
        "capture_city",
        "capture_neighborhood",
        "execute_search",
        "show_property_card",
        "property_feedback_decision",
        "refinement_decision",
    ]
    prompt: Optional[str] = None
    handler: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    transitions: List[FlowTransitionV1] = Field(default_factory=list)

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_namespaced_type(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            return v
        raw = v.strip()
        if not raw:
            return raw
        # Compatibilidade SaaS multi-domain:
        # Aceita formatos como "real_estate.execute_search" e normaliza para "execute_search".
        if "." in raw:
            return raw.split(".")[-1]
        return raw


class LeadSummaryFieldV1(BaseModel):
    key: str
    label: str
    source: str
    empty_value: Optional[str] = None


class LeadSummarySourceOptionV1(BaseModel):
    value: str
    label: str


class LeadSummaryV1(BaseModel):
    fields: List[LeadSummaryFieldV1] = Field(default_factory=list)
    source_options: Optional[List[LeadSummarySourceOptionV1]] = None


class LeadKanbanStageV1(BaseModel):
    id: str
    label: str


class LeadKanbanV1(BaseModel):
    stages: List[LeadKanbanStageV1] = Field(default_factory=list)


class ChatbotFlowDefinitionV1(BaseModel):
    version: int = 1
    start: str
    nodes: List[FlowNodeV1]
    lead_summary: Optional[LeadSummaryV1] = None
    lead_kanban: Optional[LeadKanbanV1] = None

    def node_by_id(self) -> Dict[str, FlowNodeV1]:
        return {n.id: n for n in self.nodes}

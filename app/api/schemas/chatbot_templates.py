from __future__ import annotations

from pydantic import BaseModel


class ChatbotFlowTemplateOut(BaseModel):
    domain: str
    template: str


class ChatbotFlowTemplateApplyIn(BaseModel):
    domain: str
    template: str
    name: str = "default"
    overwrite: bool = False
    publish: bool = True


class ChatbotFlowTemplateApplyOut(BaseModel):
    ok: bool = True
    flow_id: int
    published: bool
    published_version: int | None = None

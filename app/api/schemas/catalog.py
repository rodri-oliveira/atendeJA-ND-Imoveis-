from pydantic import BaseModel, ConfigDict
from typing import Any


class CatalogMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    url: str
    sort_order: int

class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    attributes: dict[str, Any]
    is_active: bool
    media: list[CatalogMediaOut] = []

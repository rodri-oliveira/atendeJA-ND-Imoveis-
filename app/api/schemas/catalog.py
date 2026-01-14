from pydantic import BaseModel, ConfigDict
from typing import Any

class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    attributes: dict[str, Any]
    is_active: bool

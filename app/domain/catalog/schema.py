from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CatalogFieldType = Literal["string", "number", "boolean", "enum", "string_list"]


class CatalogFieldDefinition(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=160)
    type: CatalogFieldType
    required: bool = False
    options: list[str] | None = None


class CatalogItemTypeSchema(BaseModel):
    fields: list[CatalogFieldDefinition] = Field(default_factory=list)

    def field_by_key(self) -> dict[str, CatalogFieldDefinition]:
        return {f.key: f for f in self.fields}


def validate_item_type_schema(*, schema: dict) -> None:
    try:
        s = CatalogItemTypeSchema.model_validate(schema or {})
    except Exception as e:
        raise ValueError(f"invalid_item_type_schema: {e}")

    seen: set[str] = set()
    for f in s.fields:
        if f.key in seen:
            raise ValueError(f"duplicate_field_key: {f.key}")
        seen.add(f.key)
        if f.type == "enum":
            opts = f.options or []
            if not opts:
                raise ValueError(f"enum_options_required: {f.key}")


def _is_number(v: Any) -> bool:
    # bool is subclass of int in Python; treat it as non-number here
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float))


def validate_attributes(*, schema: dict, attributes: dict) -> None:
    """Validates CatalogItem.attributes against CatalogItemType.schema.

    This is intentionally minimal: ensures required fields, rejects unknown fields,
    and checks primitive types.
    """

    validate_item_type_schema(schema=schema)
    s = CatalogItemTypeSchema.model_validate(schema or {})

    attrs = attributes or {}
    if not isinstance(attrs, dict):
        raise ValueError("invalid_attributes")

    fields = s.field_by_key()

    # unknown fields
    for k in attrs.keys():
        if k not in fields:
            raise ValueError(f"unknown_attribute: {k}")

    # required
    for f in fields.values():
        if f.required and f.key not in attrs:
            raise ValueError(f"required_attribute_missing: {f.key}")

    # types
    for k, v in attrs.items():
        fd = fields.get(k)
        if fd is None:
            continue
        if fd.type == "string":
            if not isinstance(v, str):
                raise ValueError(f"invalid_attribute_type: {k}")
        elif fd.type == "number":
            if not _is_number(v):
                raise ValueError(f"invalid_attribute_type: {k}")
        elif fd.type == "boolean":
            if not isinstance(v, bool):
                raise ValueError(f"invalid_attribute_type: {k}")
        elif fd.type == "string_list":
            if not isinstance(v, list) or any((not isinstance(x, str)) for x in v):
                raise ValueError(f"invalid_attribute_type: {k}")
        elif fd.type == "enum":
            if not isinstance(v, str):
                raise ValueError(f"invalid_attribute_type: {k}")
            opts = fd.options or []
            if opts and v not in opts:
                raise ValueError(f"invalid_attribute_value: {k}")

from __future__ import annotations
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import Any
import structlog

log = structlog.get_logger()


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


def _http_detail_to_code_message_details(exc: HTTPException) -> tuple[str, str, Any | None]:
    # If detail is a string, treat it as code and produce a default message
    if isinstance(exc.detail, str):
        code = exc.detail
        # Human-friendly fallback; keep it short and safe
        defaults: dict[str, str] = {
            "store_closed": "Loja fechada no momento.",
            "address_required": "Endereço é obrigatório para esta operação.",
            "menu_item_unavailable": "Item indisponível.",
            "order_not_found": "Pedido não encontrado.",
            "order_not_editable": "Pedido não pode mais ser editado.",
        }
        msg = defaults.get(code, code.replace("_", " "))
        return code, msg, None
    # If detail is dict with code/message already
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "bad_request"))
        msg = str(exc.detail.get("message", "Requisição inválida."))
        details = exc.detail.get("details")
        return code, msg, details
    # Fallback
    return "bad_request", "Requisição inválida.", None


async def http_exception_handler(request: Request, exc: HTTPException):
    code, message, details = _http_detail_to_code_message_details(exc)
    log.warning("http_error", code=code, status=exc.status_code, path=str(request.url))
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=ErrorPayload(code=code, message=message, details=details)).model_dump(),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Flatten messages briefly
    details: Any | None = None
    try:
        errs = exc.errors()
        details = errs
        fields = [".".join(str(p) for p in e.get("loc", [])) for e in errs]
        message = "Erro de validação: " + ", ".join(fields)
    except Exception:
        message = "Erro de validação nos dados enviados."
    code = "validation_error"
    log.warning("validation_error", detail=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(error=ErrorPayload(code=code, message=message, details=details)).model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    code = "internal_error"
    message = "Ocorreu um erro inesperado. Tente novamente mais tarde."
    # Log full exception for observability
    log.error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=ErrorPayload(code=code, message=message, details=None)).model_dump(),
    )

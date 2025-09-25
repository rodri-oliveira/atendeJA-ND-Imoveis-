import logging
import sys
import structlog
from typing import Any, Mapping


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    SENSITIVE_KEYS = {
        "authorization",
        "x-hub-signature-256",
        "token",
        "access_token",
        "secret",
        "signature",
        "wa_token",
        "wa_webhook_secret",
    }

    def _mask(value: str) -> str:
        if not isinstance(value, str):
            return "***"
        if len(value) <= 8:
            return "***"
        return value[:2] + "***" + value[-2:]

    def _redact_mapping(d: Mapping[str, Any]) -> dict:
        out = {}
        for k, v in d.items():
            lk = str(k).lower()
            if lk in SENSITIVE_KEYS:
                out[k] = _mask(str(v))
            elif isinstance(v, Mapping):
                out[k] = _redact_mapping(v)
            else:
                out[k] = v
        return out

    def redact_processor(logger, method_name, event_dict):  # type: ignore[no-untyped-def]
        # Redact common containers like headers/payload and flat keys
        import re

        # CPF: 11 dígitos (com ou sem máscara). Ex.: 123.456.789-09 ou 12345678909
        cpf_re = re.compile(r"(?<!\d)(\d{3})[\.\s-]?(\d{3})[\.\s-]?(\d{3})[\.\s-]?(\d{2})(?!\d)")

        def _mask_cpf_text(text: str) -> str:
            def repl(m: re.Match[str]) -> str:
                # Mantém apenas os 2 últimos dígitos
                return "***-**-**-" + m.group(4)
            try:
                return cpf_re.sub(repl, text)
            except Exception:
                return text

        def _process_value(v: Any):
            if isinstance(v, str):
                # mascara CPF em qualquer string
                return _mask_cpf_text(v)
            if isinstance(v, Mapping):
                return _redact_mapping(v)
            return v

        redacted = {}
        for k, v in event_dict.items():
            lk = str(k).lower()
            if lk in SENSITIVE_KEYS:
                redacted[k] = _mask(str(v))
            else:
                redacted[k] = _process_value(v)
        return redacted

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            timestamper,
            redact_processor,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

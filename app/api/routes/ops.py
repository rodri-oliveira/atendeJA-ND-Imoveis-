from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
import httpx
from app.core.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps import get_db, require_super_admin
from pydantic import BaseModel
from app.domain.realestate.services.funnel_service import FunnelService

router = APIRouter()


@router.get("/ping/meta", summary="Healthcheck do provider Meta Cloud (sem custo)")
async def ping_meta():
    # Valida variáveis essenciais
    problems: list[str] = []
    if not settings.WA_TOKEN:
        problems.append("WA_TOKEN ausente")
    if not settings.WA_PHONE_NUMBER_ID:
        problems.append("WA_PHONE_NUMBER_ID ausente")
    if not settings.WA_API_BASE:
        problems.append("WA_API_BASE ausente")

    checks: dict = {"env_ok": len(problems) == 0, "problems": problems}

    # Checagem leve de rede (HEAD na Graph API) – não gera custo
    try:
        url = settings.WA_API_BASE.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.head(url)
        checks["graph_head_status"] = r.status_code
        checks["graph_reachable"] = r.status_code < 500
    except Exception as e:  # noqa: BLE001
        checks["graph_reachable"] = False
        checks["error"] = str(e)

    return checks


@router.get("/config", summary="Configurações não sensíveis (observabilidade leve)")
async def config_info():
    try:
        wa_provider = getattr(settings, "WA_PROVIDER", None) or "meta"
    except Exception:
        wa_provider = "meta"
    return {
        "app_env": settings.APP_ENV,
        "wa_provider": wa_provider,
        "default_tenant": settings.DEFAULT_TENANT_ID,
        "re_read_only": bool(getattr(settings, "RE_READ_ONLY", False)),
        "version": "0.1.0",
    }


@router.get("/tenants/debug")
def tenants_debug(db: Session = Depends(get_db)):
    """Debug helper to diagnose tenant scoping and data location.

    Dev/Test: no auth required (browser-friendly).
    Prod: disabled.
    """
    if (settings.APP_ENV or "").lower() == "prod":
        raise HTTPException(status_code=403, detail="disabled_in_prod")
    # Tenants
    tenants = db.execute(text("select id, name, coalesce(is_active, true) as is_active from tenants order by id"))
    tenants_rows = [dict(r._mapping) for r in tenants]

    # Admin user
    admin = db.execute(
        text("select id, email, tenant_id, is_active from users where email = :email"),
        {"email": "admin@example.com"},
    ).fetchall()
    admin_rows = [dict(r._mapping) for r in admin]

    # Counts for common tables (ignore if missing)
    counts: dict[str, list[dict]] = {}
    for table in ["re_properties", "properties", "re_leads", "leads", "property", "lead"]:
        try:
            rows = db.execute(text(f"select tenant_id, count(1) as count from {table} group by tenant_id order by tenant_id"))
            counts[table] = [dict(r._mapping) for r in rows]
        except Exception:
            # table may not exist
            continue

    return {"tenants": tenants_rows, "admin_user": admin_rows, "counts": counts}


@router.get("/re/properties/type-counts")
def re_properties_type_counts(tenant_id: int, db: Session = Depends(get_db)):
    """Dev-only: contagem de imóveis por tipo para um tenant.

    Ajuda a validar se existem registros `house/apartment` no banco quando o filtro
    de Tipo na UI parece não funcionar.
    """
    if (settings.APP_ENV or "").lower() == "prod":
        raise HTTPException(status_code=403, detail="disabled_in_prod")
    try:
        rows = db.execute(
            text(
                """
                select type::text as tipo, count(1) as count
                from re_properties
                where tenant_id = :tenant_id and is_active = true
                group by 1
                order by 2 desc
                """
            ),
            {"tenant_id": int(tenant_id)},
        ).fetchall()
        return {"tenant_id": int(tenant_id), "type_counts": [dict(r._mapping) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "ops_type_counts_error", "message": str(e)})

class ChatbotTestIn(BaseModel):
    tenant_id: int
    wa_id: str
    text: str

@router.post("/chatbot/test")
def chatbot_test(payload: ChatbotTestIn, db: Session = Depends(get_db)):
    """Simulates an inbound message to test the chatbot funnel logic."""
    if (settings.APP_ENV or "").lower() == "prod":
        raise HTTPException(status_code=403, detail="disabled_in_prod")

    try:
        funnel_service = FunnelService(db=db)
        response_text = funnel_service.process_message(
            tenant_id=payload.tenant_id,
            wa_id=payload.wa_id,
            user_text=payload.text
        )
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "ops_chatbot_test_error", "message": str(e)})

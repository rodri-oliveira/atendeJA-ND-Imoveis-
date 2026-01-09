from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from app.api.errors import http_exception_handler, validation_exception_handler, generic_exception_handler
from app.core.config import settings
from app.core.logging import configure_logging
from app.api.routes.health import router as health_router
from app.api.routes.ops import router as ops_router
from app.api.routes.webhook import router as webhook_router
from app.api.routes.admin import router as admin_router
from app.api.routes.realestate import router as realestate_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.admin_realestate import router as admin_realestate_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.llm import router as llm_router
from app.api.routes.auth import router as auth_router
from app.api.routes.super_admin import router as super_admin_router
from app.repositories.db import db_session, engine
from app.api.deps import get_db

from app.repositories.models import Base, User, UserRole, Tenant
import app.domain.realestate.models  # noqa: F401 - importa modelos para registrar no metadata
from app.domain.realestate.models import ChatbotFlow
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.domain.realestate.default_flow import get_default_flow_nodes
from contextlib import asynccontextmanager
import structlog
import traceback
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.security import get_password_hash

configure_logging()
log = structlog.get_logger()
log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if (settings.APP_ENV or "").lower() == "test":
        # Em testes, garantir schema limpo para isolar dados entre execuções
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception as e:
            log.warning("metadata_drop_error", error=str(e))
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            log.error("metadata_create_error", error=str(e))
    else:
        Base.metadata.create_all(bind=engine)
        # Garante que exista tenant_id=1 em dev/test (evita 404 quando o front usa tenantId=1)
        try:
            with db_session() as db:  # type: Session
                env = (settings.APP_ENV or "").lower()
                if env in {"dev", "test"}:
                    t1 = db.get(Tenant, 1)
                    if not t1:

                        # Evitar conflito de nome único
                        name = "Default"
                        exists_by_name = db.query(Tenant).filter(Tenant.name == name).first()
                        if exists_by_name:
                            name = "Default (1)"
                        t = Tenant(id=1, name=name)
                        db.add(t)
                        db.commit()
                        t1 = t
                    # Garantir tenant 1 ativo
                    if t1 is not None and not bool(getattr(t1, "is_active", True)):
                        t1.is_active = True
                        db.add(t1)
                        db.commit()

                    # Em dev/test, se existir base de imóveis em outro tenant, manter o admin no tenant com dados.
                    # Isso evita "lista vazia" após migração/multi-tenant.
                    try:
                        rows = db.execute(text("select tenant_id, count(1) as c from re_properties group by tenant_id order by c desc")).fetchall()
                        if rows:
                            data_tenant_id = int(rows[0][0])
                            if data_tenant_id:
                                data_tenant = db.get(Tenant, data_tenant_id)
                                if data_tenant is not None and not bool(getattr(data_tenant, "is_active", True)):
                                    data_tenant.is_active = True
                                    db.add(data_tenant)
                                    db.commit()

                                u = db.query(User).filter(User.email == "admin@example.com").first()
                                if u and u.tenant_id is not None and int(u.tenant_id) != data_tenant_id:
                                    u.tenant_id = data_tenant_id
                                    db.add(u)
                                    db.commit()
                    except Exception:
                        # tabela pode não existir em instalações novas
                        db.rollback()

                    # Seed do flow default (Flow as Data) em dev/test
                    try:
                        existing = (
                            db.query(ChatbotFlow)
                            .filter(
                                ChatbotFlow.tenant_id == int(t1.id),
                                ChatbotFlow.domain == "real_estate",
                                ChatbotFlow.is_published == True,  # noqa: E712
                            )
                            .first()
                        )
                        flow_definition = {
                            "version": 1,
                            "start": "start",
                            "nodes": get_default_flow_nodes(),
                        }

                        flow_service = ChatbotFlowService(db=db)
                        flow_service.validate_definition(flow_definition)

                        if not existing:
                            f = ChatbotFlow(
                                tenant_id=int(t1.id),
                                domain="real_estate",
                                name="default",
                                flow_definition=flow_definition,
                                is_published=True,
                                published_version=1,
                                published_by="bootstrap",
                            )
                            db.add(f)
                            db.commit()
                            log.info("chatbot_flow_seeded", tenant_id=int(t1.id), name=f.name)
                        else:
                            is_bootstrap_flow = (
                                (getattr(existing, "published_by", None) == "bootstrap")
                                or (getattr(existing, "name", None) == "default")
                            )
                            if is_bootstrap_flow:
                                try:
                                    nodes = (existing.flow_definition or {}).get("nodes") or []
                                    node_by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}

                                    def _node_type(node_id: str) -> str:
                                        raw = (node_by_id.get(node_id) or {}).get("type") or ""
                                        try:
                                            s = str(raw).strip()
                                        except Exception:
                                            return ""
                                        if "." in s:
                                            return s.split(".")[-1]
                                        return s

                                    has_new_node_has_property = (
                                        _node_type("awaiting_has_property_in_mind") == "prompt_and_branch"
                                    )
                                    has_new_node_search_choice = (
                                        _node_type("awaiting_search_choice") == "prompt_and_branch"
                                    )
                                    has_new_node_schedule_visit = (
                                        _node_type("awaiting_schedule_visit_question") == "prompt_and_branch"
                                    )
                                    has_new_node_phone_confirmation = (
                                        _node_type("awaiting_phone_confirmation") == "prompt_and_branch"
                                    )
                                    has_new_node_phone_input = (
                                        _node_type("awaiting_phone_input") == "capture_phone"
                                    )
                                    has_new_node_visit_date = (
                                        _node_type("awaiting_visit_date") == "capture_date"
                                    )
                                    has_new_node_visit_time = (
                                        _node_type("awaiting_visit_time") == "capture_time"
                                    )
                                    has_new_node_purpose = (
                                        _node_type("awaiting_purpose") == "capture_purpose"
                                    )
                                    has_new_node_type = (
                                        _node_type("awaiting_type") == "capture_property_type"
                                    )
                                    has_new_node_price_min = (
                                        _node_type("awaiting_price_min") == "capture_price_min"
                                    )
                                    has_new_node_price_max = (
                                        _node_type("awaiting_price_max") == "capture_price_max"
                                    )
                                    has_new_node_bedrooms = (
                                        _node_type("awaiting_bedrooms") == "capture_bedrooms"
                                    )
                                    has_new_node_city = (
                                        _node_type("awaiting_city") == "capture_city"
                                    )
                                    has_new_node_neighborhood = (
                                        _node_type("awaiting_neighborhood") == "capture_neighborhood"
                                    )
                                    has_new_node_searching = (
                                        _node_type("searching") == "execute_search"
                                    )
                                    has_new_node_showing_property = (
                                        _node_type("showing_property") == "show_property_card"
                                    )
                                    has_new_node_property_feedback = (
                                        _node_type("awaiting_property_feedback") == "property_feedback_decision"
                                    )
                                    has_new_node_refinement = (
                                        _node_type("awaiting_refinement") == "refinement_decision"
                                    )
                                    has_new_nodes = bool(
                                        has_new_node_has_property
                                        and has_new_node_search_choice
                                        and has_new_node_schedule_visit
                                        and has_new_node_phone_confirmation
                                        and has_new_node_phone_input
                                        and has_new_node_visit_date
                                        and has_new_node_visit_time
                                        and has_new_node_purpose
                                        and has_new_node_type
                                        and has_new_node_price_min
                                        and has_new_node_price_max
                                        and has_new_node_bedrooms
                                        and has_new_node_city
                                        and has_new_node_neighborhood
                                        and has_new_node_searching
                                        and has_new_node_showing_property
                                        and has_new_node_property_feedback
                                        and has_new_node_refinement
                                    )
                                except Exception:
                                    has_new_nodes = False

                                if not has_new_nodes:
                                    existing.flow_definition = flow_definition
                                    existing.published_version = int(getattr(existing, "published_version", 1) or 1) + 1
                                    existing.published_by = "bootstrap"
                                    db.add(existing)
                                    db.commit()
                                    log.info(
                                        "chatbot_flow_seed_migrated",
                                        tenant_id=int(t1.id),
                                        name=getattr(existing, "name", None),
                                        published_version=int(getattr(existing, "published_version", 0) or 0),
                                    )
                    except Exception as e:
                        log.warning("chatbot_flow_seed_error", error=str(e))
                else:
                    first_tenant = db.query(Tenant).order_by(Tenant.id.asc()).first()
                    if not first_tenant:
                        t = Tenant(name="Default")
                        db.add(t)
                        db.commit()
        except Exception as e:
            log.error("tenant_bootstrap_error", error=str(e))
        # Seed do usuário admin, se configurado
        try:
            seed_email = (settings.AUTH_SEED_ADMIN_EMAIL or "").strip().lower()
            seed_password = (settings.AUTH_SEED_ADMIN_PASSWORD or "").strip()
            if seed_email and seed_password:
                with db_session() as db:  # type: Session
                    tenant = db.query(Tenant).order_by(Tenant.id.asc()).first()
                    if not tenant:
                        tenant = Tenant(name="Default")
                        db.add(tenant)
                        db.commit()
                        db.refresh(tenant)

                    user = db.query(User).filter(User.email == seed_email).first()
                    if not user:
                        user = User(
                            email=seed_email,
                            full_name="Admin",
                            hashed_password=get_password_hash(seed_password),
                            is_active=True,
                            role=UserRole.admin,
                            tenant_id=int(tenant.id),
                        )
                        db.add(user)
                        db.commit()
                        log.info("admin_seeded", email=seed_email)
                    elif getattr(user, "tenant_id", None) is None and tenant is not None:
                        user.tenant_id = int(tenant.id)
                        db.add(user)
                        db.commit()
        except Exception as e:
            log.error("admin_seed_error", error=str(e))
    yield
    # Shutdown: nothing for now


tags_metadata = [
    {"name": "health", "description": "Healthchecks de liveness/readiness."},
    {"name": "webhook", "description": "Webhook do WhatsApp Cloud API."},
    {"name": "ops", "description": "Operações e healthchecks de integrações."},
    {"name": "admin", "description": "Endpoints administrativos (futuros)."},
    {"name": "realestate", "description": "Domínio imobiliário: imóveis e leads."},
    {"name": "auth", "description": "Autenticação JWT e informações do usuário."},
    {"name": "super-admin", "description": "Endpoints de super-administração para onboarding de locatários."},
]

app = FastAPI(
    title="AtendeJá Chatbot API",
    version="0.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.dependency_overrides[get_db] = get_db

@app.middleware("http")
async def _http_logger(request, call_next):
    try:
        # Correlation ID (propaga entre logs e resposta)
        cid = request.headers.get("x-correlation-id")
        if not cid:
            import uuid

            cid = str(uuid.uuid4())
        try:
            body_bytes = await request.body()
        except Exception:
            body_bytes = b""
        log.info(
            "http_request_start",
            method=request.method,
            path=request.url.path,
            content_type=request.headers.get("content-type"),
            content_length=len(body_bytes) if body_bytes is not None else 0,
            correlation_id=cid,
        )
        response = await call_next(request)
        try:
            response.headers["X-Correlation-Id"] = cid
        except Exception:
            pass
        log.info(
            "http_request_end",
            method=request.method,
            path=request.url.path,
            status=getattr(response, "status_code", None),
            correlation_id=cid,
        )
        return response
    except Exception as e:
        log.error(
            "http_request_exception",
            method=request.method,
            path=request.url.path,
            error=str(e),
            traceback=traceback.format_exc(),
            correlation_id=request.headers.get("x-correlation-id"),
        )
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "unexpected error"}})

app.include_router(health_router, prefix="/health", tags=["health"]) 
app.include_router(ops_router, prefix="/ops", tags=["ops"]) 
app.include_router(webhook_router, prefix="/webhook", tags=["webhook"]) 
app.include_router(admin_router, prefix="/admin", tags=["admin"]) 
app.include_router(realestate_router, prefix="/re", tags=["realestate"]) 
app.include_router(mcp_router, prefix="/api/v1/mcp", tags=["mcp"]) 
app.include_router(auth_router, prefix="/auth", tags=["auth"]) 
app.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
app.include_router(llm_router, prefix="/llm", tags=["llm"]) 
app.include_router(admin_realestate_router, prefix="/admin/re", tags=["admin-re"]) 
app.include_router(super_admin_router, tags=["super-admin"])

# Servir uploads locais (MVP). Estrutura esperada: /static/imoveis/{tenant_id}/{property_id}/{filename}.
# Em produção usar CDN/Storage dedicado.

try:
    import os
    from pathlib import Path
    uploads_path = Path("uploads") / "imoveis"
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static/imoveis", StaticFiles(directory=str(uploads_path), html=False), name="static-imoveis")
except Exception as e:
    log.warning("mount_static_error", error=str(e))

# Global error handlers (uniform error payloads)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

@app.get("/")
async def root():
    return {"service": "atendeja-chatbot", "status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
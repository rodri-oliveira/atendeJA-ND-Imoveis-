from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.repositories.models import Tenant, WhatsAppAccount, UserRole, User, OnboardingRun

from app.api.schemas.chatbot_templates import ChatbotFlowTemplateApplyIn
from app.services.chatbot_template_service import apply_chatbot_flow_template, list_chatbot_flow_templates
from app.services.tenant_onboarding_service import TenantOnboardingService
from app.core.config import settings
from app.domain.catalog.models import CatalogIngestionRun, CatalogIngestionError
from app.services.vehicle_ingestion_jobs import run_vehicle_ingestion_job

router = APIRouter(prefix="/super", dependencies=[Depends(require_super_admin)])


class ChatbotTemplateOut(BaseModel):
    domain: str
    template: str


@router.get("/chatbot-templates", response_model=list[ChatbotTemplateOut])
def list_super_chatbot_templates():
    return list_chatbot_flow_templates()


class OnboardingRunOut(BaseModel):
    id: int
    idempotency_key: str
    status: str
    tenant_id: int | None
    request_json: dict
    response_json: dict | None
    error_code: str | None
    created_at: str
    updated_at: str


@router.get("/onboarding-runs/{idempotency_key}", response_model=OnboardingRunOut)
def get_onboarding_run(idempotency_key: str, db: Session = Depends(get_db)):
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="idempotency_key_required")
    row = db.query(OnboardingRun).filter(OnboardingRun.idempotency_key == key).first()
    if not row:
        raise HTTPException(status_code=404, detail="onboarding_run_not_found")
    return OnboardingRunOut(
        id=int(row.id),
        idempotency_key=str(row.idempotency_key),
        status=str(row.status),
        tenant_id=(int(row.tenant_id) if row.tenant_id is not None else None),
        request_json=dict(row.request_json or {}),
        response_json=(dict(row.response_json or {}) if row.response_json is not None else None),
        error_code=(str(row.error_code) if row.error_code is not None else None),
        created_at=row.created_at.isoformat() if getattr(row, "created_at", None) else "",
        updated_at=row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
    )


class TenantCreateIn(BaseModel):
    name: str
    timezone: str = "America/Sao_Paulo"


class TenantOut(BaseModel):
    id: int
    name: str
    timezone: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TenantUpdateIn(BaseModel):
    name: str | None = None
    timezone: str | None = None
    settings_json: dict | None = None
    is_active: bool | None = None


@router.post("/tenants", response_model=TenantOut)
def create_tenant(payload: TenantCreateIn, db: Session = Depends(get_db)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    exists = db.query(Tenant).filter(Tenant.name == name).first()
    if exists:
        raise HTTPException(status_code=400, detail="tenant_name_already_exists")
    t = Tenant(name=name, timezone=(payload.timezone or "America/Sao_Paulo"))
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.id.asc()).all()


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: int, payload: TenantUpdateIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name_required")
        exists = db.query(Tenant).filter(Tenant.name == name, Tenant.id != t.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="tenant_name_already_exists")
        t.name = name
    if "timezone" in data and data["timezone"] is not None:
        t.timezone = str(data["timezone"]).strip() or t.timezone
    if "settings_json" in data and data["settings_json"] is not None:
        t.settings_json = data["settings_json"]
    if "is_active" in data and data["is_active"] is not None:
        t.is_active = bool(data["is_active"])
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


class WhatsAppAccountCreateIn(BaseModel):
    phone_number_id: str
    token: str | None = None
    waba_id: str | None = None
    is_active: bool = True


class WhatsAppAccountOut(BaseModel):
    id: int
    tenant_id: int
    phone_number_id: str
    waba_id: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.post("/tenants/{tenant_id}/whatsapp-accounts", response_model=WhatsAppAccountOut)
def create_whatsapp_account(tenant_id: int, payload: WhatsAppAccountCreateIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    phone_number_id = (payload.phone_number_id or "").strip()
    if not phone_number_id:
        raise HTTPException(status_code=400, detail="phone_number_id_required")
    exists = db.query(WhatsAppAccount).filter(WhatsAppAccount.phone_number_id == phone_number_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="phone_number_id_already_exists")
    acc = WhatsAppAccount(
        tenant_id=t.id,
        phone_number_id=phone_number_id,
        token=(payload.token or None),
        waba_id=(payload.waba_id or None),
        is_active=bool(payload.is_active),
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/tenants/{tenant_id}/whatsapp-accounts", response_model=list[WhatsAppAccountOut])
def list_whatsapp_accounts(tenant_id: int, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    return db.query(WhatsAppAccount).filter(WhatsAppAccount.tenant_id == t.id).order_by(WhatsAppAccount.id.asc()).all()


class InviteAdminIn(BaseModel):
    email: str
    expires_hours: int = Field(default=72, ge=1, le=168)


class InviteAdminOut(BaseModel):
    token: str
    email: str
    tenant_id: int
    role: str


@router.post("/tenants/{tenant_id}/invite-admin", response_model=InviteAdminOut)
def invite_tenant_admin(tenant_id: int, payload: InviteAdminIn, db: Session = Depends(get_db)):
    # Reutiliza endpoint admin existente via import local para evitar circular
    from app.api.routes.admin import _issue_invite

    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email_required")

    out = _issue_invite(db, email=email, role=UserRole.admin, tenant_id=int(t.id), expires_hours=int(payload.expires_hours))
    return InviteAdminOut(token=out.token, email=out.email, tenant_id=int(t.id), role=UserRole.admin.value)


class AssignUserIn(BaseModel):
    email: str


class AssignUserOut(BaseModel):
    user_id: int
    email: str
    tenant_id: int


@router.post("/tenants/{tenant_id}/assign-user", response_model=AssignUserOut)
def assign_user_to_tenant(tenant_id: int, payload: AssignUserIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email_required")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user.tenant_id = int(t.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return AssignUserOut(user_id=int(user.id), email=str(user.email), tenant_id=int(user.tenant_id or 0))


class TenantOnboardByUrlIn(BaseModel):
    idempotency_key: str | None = None
    name: str
    timezone: str = "America/Sao_Paulo"
    chatbot_domain: str = "real_estate"

    allow_existing: bool = False

    template: str = "default"
    flow_name: str = "default"
    overwrite_flow: bool = True
    publish_flow: bool = True

    base_url: str | None = None
    run_ingestion: bool = False
    max_listings: int = Field(30, ge=1, le=200)
    timeout_seconds: float = Field(10.0, ge=2.0, le=60.0)
    max_listing_pages: int = Field(4, ge=0, le=20)

    create_whatsapp_account: bool = False
    phone_number_id: str | None = None
    waba_id: str | None = None
    token: str | None = None

    invite_admin_email: str | None = None
    invite_expires_hours: int = Field(default=72, ge=1, le=168)


class TenantOnboardByUrlOut(BaseModel):
    tenant_id: int
    tenant_name: str
    chatbot_domain: str
    flow_id: int
    published: bool
    published_version: int | None = None
    ingestion: dict | None = None
    whatsapp_account_id: int | None = None
    invite_token: str | None = None
    invite_email: str | None = None


class OnboardingEnsureTenantIn(BaseModel):
    name: str
    timezone: str = "America/Sao_Paulo"
    chatbot_domain: str = "real_estate"
    allow_existing: bool = False


class OnboardingEnsureTenantOut(BaseModel):
    tenant_id: int
    tenant_name: str
    timezone: str
    chatbot_domain: str


@router.post("/onboarding/steps/ensure-tenant", response_model=OnboardingEnsureTenantOut)
def onboarding_step_ensure_tenant(payload: OnboardingEnsureTenantIn, db: Session = Depends(get_db)):
    svc = TenantOnboardingService(db=db)
    try:
        t = svc.ensure_tenant(
            name=payload.name,
            timezone=payload.timezone,
            chatbot_domain=payload.chatbot_domain,
            allow_existing=bool(payload.allow_existing),
        )
        db.commit()
        db.refresh(t)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    settings_json = dict(getattr(t, "settings_json", {}) or {})
    return OnboardingEnsureTenantOut(
        tenant_id=int(t.id),
        tenant_name=str(t.name),
        timezone=str(getattr(t, "timezone", "America/Sao_Paulo") or "America/Sao_Paulo"),
        chatbot_domain=str(settings_json.get("chatbot_domain") or (payload.chatbot_domain or "real_estate")),
    )


class OnboardingApplyFlowTemplateIn(BaseModel):
    chatbot_domain: str = "real_estate"
    template: str = "default"
    flow_name: str = "default"
    overwrite_flow: bool = True
    publish_flow: bool = True


class OnboardingApplyFlowTemplateOut(BaseModel):
    tenant_id: int
    chatbot_domain: str
    flow_id: int
    published: bool
    published_version: int | None = None


@router.post("/onboarding/steps/tenants/{tenant_id}/apply-flow-template", response_model=OnboardingApplyFlowTemplateOut)
def onboarding_step_apply_flow_template(tenant_id: int, payload: OnboardingApplyFlowTemplateIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    svc = TenantOnboardingService(db=db)
    try:
        out = svc.apply_flow_template(
            tenant_id=int(t.id),
            chatbot_domain=payload.chatbot_domain,
            template=payload.template,
            flow_name=payload.flow_name,
            overwrite_flow=bool(payload.overwrite_flow),
            publish_flow=bool(payload.publish_flow),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    domain = (payload.chatbot_domain or "").strip() or "real_estate"
    return OnboardingApplyFlowTemplateOut(
        tenant_id=int(t.id),
        chatbot_domain=domain,
        flow_id=int(out.flow_id),
        published=bool(out.published),
        published_version=(int(out.published_version) if out.published_version is not None else None),
    )


class OnboardingCreateWhatsAppAccountIn(BaseModel):
    phone_number_id: str
    token: str | None = None
    waba_id: str | None = None


class OnboardingCreateWhatsAppAccountOut(BaseModel):
    tenant_id: int
    whatsapp_account_id: int
    phone_number_id: str


@router.post(
    "/onboarding/steps/tenants/{tenant_id}/create-whatsapp-account",
    response_model=OnboardingCreateWhatsAppAccountOut,
)
def onboarding_step_create_whatsapp_account(tenant_id: int, payload: OnboardingCreateWhatsAppAccountIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    svc = TenantOnboardingService(db=db)
    try:
        wa_id = svc.create_whatsapp_account(
            tenant_id=int(t.id),
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            token=payload.token,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return OnboardingCreateWhatsAppAccountOut(
        tenant_id=int(t.id),
        whatsapp_account_id=int(wa_id),
        phone_number_id=str(payload.phone_number_id),
    )


class OnboardingInviteAdminIn(BaseModel):
    email: str
    expires_hours: int = Field(default=72, ge=1, le=168)


class OnboardingInviteAdminOut(BaseModel):
    tenant_id: int
    email: str
    token: str


@router.post("/onboarding/steps/tenants/{tenant_id}/invite-admin", response_model=OnboardingInviteAdminOut)
def onboarding_step_invite_admin(tenant_id: int, payload: OnboardingInviteAdminIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    svc = TenantOnboardingService(db=db)
    try:
        token, email = svc.invite_admin(
            tenant_id=int(t.id),
            invite_admin_email=payload.email,
            invite_expires_hours=int(payload.expires_hours),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return OnboardingInviteAdminOut(tenant_id=int(t.id), email=str(email), token=str(token))


class OnboardingEnqueueIngestionIn(BaseModel):
    base_url: str = Field(..., min_length=3)
    max_listings: int = Field(30, ge=1, le=200)
    timeout_seconds: float = Field(10.0, ge=2.0, le=60.0)
    max_listing_pages: int = Field(4, ge=0, le=20)


class OnboardingEnqueueIngestionOut(BaseModel):
    tenant_id: int
    run_id: int
    status: str


@router.post(
    "/onboarding/steps/tenants/{tenant_id}/enqueue-ingestion",
    response_model=OnboardingEnqueueIngestionOut,
)
def onboarding_step_enqueue_ingestion(
    tenant_id: int,
    payload: OnboardingEnqueueIngestionIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")

    svc = TenantOnboardingService(db=db)
    out = svc.enqueue_ingestion(
        tenant_id=int(t.id),
        base_url=str(payload.base_url),
        max_listings=int(payload.max_listings),
        timeout_seconds=float(payload.timeout_seconds),
        max_listing_pages=int(payload.max_listing_pages),
        background_tasks=bg,
    )
    return OnboardingEnqueueIngestionOut(tenant_id=int(t.id), run_id=int(out["run_id"]), status=str(out["status"]))


@router.post("/onboarding/by-url", response_model=TenantOnboardByUrlOut)
async def onboard_tenant_by_url(payload: TenantOnboardByUrlIn, bg: BackgroundTasks, db: Session = Depends(get_db)):
    svc = TenantOnboardingService(db=db)
    out = await svc.onboard_by_url(
        idempotency_key=payload.idempotency_key,
        name=payload.name,
        timezone=payload.timezone,
        chatbot_domain=payload.chatbot_domain,
        allow_existing=bool(payload.allow_existing),
        template=payload.template,
        flow_name=payload.flow_name,
        overwrite_flow=bool(payload.overwrite_flow),
        publish_flow=bool(payload.publish_flow),
        base_url=payload.base_url,
        run_ingestion=bool(payload.run_ingestion),
        max_listings=int(payload.max_listings),
        timeout_seconds=float(payload.timeout_seconds),
        max_listing_pages=int(payload.max_listing_pages),
        create_whatsapp_account=bool(payload.create_whatsapp_account),
        phone_number_id=payload.phone_number_id,
        waba_id=payload.waba_id,
        token=payload.token,
        invite_admin_email=payload.invite_admin_email,
        invite_expires_hours=int(payload.invite_expires_hours),
        background_tasks=bg,
    )

    return TenantOnboardByUrlOut(
        tenant_id=int(out.tenant_id),
        tenant_name=str(out.tenant_name),
        chatbot_domain=str(out.chatbot_domain),
        flow_id=int(out.flow_id),
        published=bool(out.published),
        published_version=(int(out.published_version) if out.published_version is not None else None),
        ingestion=out.ingestion,
        whatsapp_account_id=(int(out.whatsapp_account_id) if out.whatsapp_account_id is not None else None),
        invite_token=(str(out.invite_token) if out.invite_token is not None else None),
        invite_email=(str(out.invite_email) if out.invite_email is not None else None),
    )


class VehicleIngestionEnqueueIn(BaseModel):
    base_url: str = Field(..., min_length=3)
    max_listings: int = Field(30, ge=1, le=200)
    timeout_seconds: float = Field(10.0, ge=2.0, le=60.0)
    max_listing_pages: int = Field(4, ge=0, le=20)


class VehicleIngestionEnqueueOut(BaseModel):
    run_id: int
    status: str


class VehicleIngestionRunOut(BaseModel):
    run_id: int
    tenant_id: int
    status: str
    discovered: int
    processed: int
    created: int
    updated: int
    errors: int
    started_at: str
    finished_at: str | None


@router.post("/tenants/{tenant_id}/ingestion/vehicles/enqueue", response_model=VehicleIngestionEnqueueOut)
def enqueue_vehicle_ingestion_run(tenant_id: int, payload: VehicleIngestionEnqueueIn, bg: BackgroundTasks, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    run = CatalogIngestionRun(tenant_id=int(t.id), source_base_url=str(payload.base_url), status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)

    if (settings.APP_ENV or "").lower() != "test":
        bg.add_task(
            run_vehicle_ingestion_job,
            tenant_id=int(t.id),
            run_id=int(run.id),
            base_url=str(payload.base_url),
            max_listings=int(payload.max_listings),
            timeout_seconds=float(payload.timeout_seconds),
            max_listing_pages=int(payload.max_listing_pages),
        )

    return VehicleIngestionEnqueueOut(run_id=int(run.id), status=str(run.status))


@router.get("/tenants/{tenant_id}/ingestion/runs/{run_id}", response_model=VehicleIngestionRunOut)
def get_vehicle_ingestion_run(tenant_id: int, run_id: int, db: Session = Depends(get_db)):
    t = db.get(Tenant, int(tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    run = db.get(CatalogIngestionRun, int(run_id))
    if not run or int(run.tenant_id) != int(t.id):
        raise HTTPException(status_code=404, detail="run_not_found")

    errors = (
        db.query(CatalogIngestionError)
        .filter(CatalogIngestionError.run_id == int(run.id))
        .count()
    )
    return VehicleIngestionRunOut(
        run_id=int(run.id),
        tenant_id=int(run.tenant_id),
        status=str(run.status),
        discovered=int(run.discovered_count or 0),
        processed=int(run.processed_count or 0),
        created=int(run.created_count or 0),
        updated=int(run.updated_count or 0),
        errors=int(errors),
        started_at=run.started_at.isoformat() if getattr(run, "started_at", None) else "",
        finished_at=run.finished_at.isoformat() if getattr(run, "finished_at", None) else None,
    )

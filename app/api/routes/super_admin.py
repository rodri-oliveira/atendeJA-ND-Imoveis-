from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.repositories.models import Tenant, WhatsAppAccount, UserRole, User

router = APIRouter(prefix="/super", dependencies=[Depends(require_super_admin)])


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

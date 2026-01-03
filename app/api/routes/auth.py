from datetime import timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.repositories.models import User, UserInvite, UserRole, Tenant

router = APIRouter()


class AcceptInviteIn(BaseModel):
    token: str
    password: str
    full_name: str | None = None


class AcceptInviteOut(BaseModel):
    user_id: int
    email: str
    tenant_id: int
    role: UserRole
    activated: bool


@router.post("/login", summary="Realiza login e retorna um token JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # No nosso caso, usamos email como username
    email = form_data.username.strip().lower()
    user: User | None = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_credentials")

    if user.tenant_id is not None:
        tenant = db.get(Tenant, int(user.tenant_id))
        if not tenant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_not_found")
        if not bool(getattr(tenant, "is_active", True)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_suspended")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_credentials")

    access_token = create_access_token(
        subject=user.email,
        expires_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
        extra={"role": user.role.value, "tenant_id": user.tenant_id},
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", summary="Retorna o usuário logado (a partir do token)")
def read_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "tenant_id": current_user.tenant_id,
    }


@router.post("/accept_invite", response_model=AcceptInviteOut)
def accept_invite(payload: AcceptInviteIn, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    inv: UserInvite | None = db.query(UserInvite).filter(UserInvite.token == token).first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    if inv.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invite_used")
    if inv.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invite_expired")

    email = (inv.email or "").strip().lower()
    user: User | None = db.query(User).filter(User.email == email).first()
    from app.core.security import get_password_hash

    if user:
        if user.tenant_id is not None and int(user.tenant_id) != int(inv.tenant_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email_in_other_tenant")
        user.hashed_password = get_password_hash(payload.password)
        user.full_name = payload.full_name or user.full_name
        user.role = inv.role
        user.is_active = True
        user.tenant_id = inv.tenant_id if user.tenant_id is None else user.tenant_id
        db.add(user)
    else:
        user = User(
            email=email,
            full_name=payload.full_name,
            hashed_password=get_password_hash(payload.password),
            is_active=True,
            role=inv.role,
            tenant_id=inv.tenant_id,
        )
        db.add(user)
    inv.used_at = datetime.utcnow()
    db.add(inv)
    db.commit()
    db.refresh(user)
    return AcceptInviteOut(
        user_id=user.id,
        email=user.email,
        tenant_id=int(user.tenant_id or 0),
        role=user.role,
        activated=user.is_active,
    )

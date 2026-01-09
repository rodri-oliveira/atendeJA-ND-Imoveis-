from typing import Annotated, Literal

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from dataclasses import dataclass

from app.core.security import decode_token
from app.repositories.db import db_session
from app.repositories.models import User, UserRole, Tenant
import redis
from app.core.config import settings
from app.services.conversation_state import ConversationStateService

# Pool de conexões com o Redis para reutilização
_redis_pool = None

def get_redis_client() -> redis.Redis:
    """
    Fornece um cliente Redis a partir de um pool de conexões, garantindo eficiência.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
    return redis.Redis(connection_pool=_redis_pool)


def get_conversation_state_service(
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)]
) -> ConversationStateService:
    """
    Fornece uma instância do serviço de gerenciamento de estado da conversa.
    """
    return ConversationStateService(redis_client=redis_client)



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Session:
    with db_session() as db:
        yield db


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    user: User | None = db.query(User).filter(User.email == sub).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive_or_not_found")
    return user


def require_role_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_only")
    return user


async def get_optional_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> User | None:
    if not authorization:
        return None
    raw = str(authorization).strip()
    if not raw:
        return None
    if not raw.lower().startswith("bearer "):
        return None
    token = raw.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    user: User | None = db.query(User).filter(User.email == sub).first()
    if not user or not user.is_active:
        return None
    return user


def require_admin_or_super_admin(
    user: Annotated[User | None, Depends(get_optional_user)],
    x_super_admin_key: Annotated[str | None, Header(alias="X-Super-Admin-Key")] = None,
) -> User | None:
    expected = (settings.SUPER_ADMIN_API_KEY or "").strip()
    if not expected:
        env = (settings.APP_ENV or "").lower()
        if env in {"dev", "test"}:
            expected = "dev"
    if expected and (x_super_admin_key or "").strip() == expected:
        return None

    if user is None:
        env = (settings.APP_ENV or "").lower()
        if env == "test":
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_only")
    return user


def get_tenant_id(x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None) -> int:
    """Resolve tenant_id for HTTP routes.

    Production: header is mandatory.
    Dev/Test: header is optional (falls back to DEFAULT_TENANT_ID when numeric, else 1).
    """
    env = (settings.APP_ENV or "").lower()
    if x_tenant_id:
        try:
            return int(str(x_tenant_id).strip())
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_tenant_id")

    if env == "prod":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_tenant_id")

    # Dev/Test fallback
    try:
        return int(str(settings.DEFAULT_TENANT_ID).strip())
    except Exception:
        return 1


def require_active_tenant(
    tenant_id: Annotated[int, Depends(get_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> int:
    tenant = db.get(Tenant, int(tenant_id))
    if not tenant:
        env = (settings.APP_ENV or "").lower()
        if env == "test":
            tenant = Tenant(id=int(tenant_id), name=f"tenant-{int(tenant_id)}")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
    if not bool(getattr(tenant, "is_active", True)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_suspended")
    return int(tenant_id)


def require_tenant_admin_or_super_admin(
    tenant_id: Annotated[int, Depends(require_active_tenant)],
    user: Annotated[User | None, Depends(require_admin_or_super_admin)],
) -> int:
    if user is None:
        return int(tenant_id)
    if user.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_assigned_to_tenant")
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cross_tenant_forbidden")
    return int(tenant_id)


@dataclass(frozen=True)
class RequestContext:
    actor: Literal["public", "admin_user", "super_admin"]
    tenant_id: int
    user: User | None = None
    role: UserRole | None = None


def require_admin_request_context(
    tenant_id: Annotated[int, Depends(require_active_tenant)],
    user: Annotated[User | None, Depends(require_admin_or_super_admin)],
) -> RequestContext:
    if user is None:
        return RequestContext(actor="super_admin", tenant_id=int(tenant_id), user=None, role=None)
    if user.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_assigned_to_tenant")
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cross_tenant_forbidden")
    return RequestContext(actor="admin_user", tenant_id=int(tenant_id), user=user, role=user.role)


def require_active_tenant_context(
    tenant_id: Annotated[int, Depends(require_active_tenant)],
) -> RequestContext:
    return RequestContext(actor="public", tenant_id=int(tenant_id), user=None, role=None)


def require_admin_tenant_id(
    ctx: Annotated[RequestContext, Depends(require_admin_request_context)],
) -> int:
    return int(ctx.tenant_id)


def require_super_admin(
    x_super_admin_key: Annotated[str | None, Header(alias="X-Super-Admin-Key")] = None,
) -> None:
    expected = (settings.SUPER_ADMIN_API_KEY or "").strip()
    if not expected:
        env = (settings.APP_ENV or "").lower()
        if env in {"dev", "test"}:
            expected = "dev"
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="super_admin_not_configured")
    provided = (x_super_admin_key or "").strip()
    if provided != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="super_admin_only")

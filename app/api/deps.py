from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.repositories.db import SessionLocal
from app.repositories.models import User, UserRole
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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Ajuste para SQLite em desenvolvimento: evitar erro de threads do SQLite
kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    kwargs["connect_args"] = {"check_same_thread": False}
    # Em memória, garantir que a mesma conexão seja usada em todas as sessoes
    if settings.DATABASE_URL == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool

engine = create_engine(settings.DATABASE_URL, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

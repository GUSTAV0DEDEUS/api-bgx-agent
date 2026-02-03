from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.utils.settings import settings


Base = declarative_base()

# Engine e SessionLocal são inicializados lazy
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def SessionLocal() -> Session:
    """Retorna uma nova sessão do banco de dados."""
    return _get_session_local()()


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI para injeção de sessão do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

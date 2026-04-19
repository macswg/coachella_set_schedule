from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def sqlite_url(path: str | None = None) -> str:
    target = Path(path or settings.SQLITE_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target}"


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(sqlite_url(), future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_session() -> Iterator[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables if missing. Called on startup when DATA_BACKEND=sqlite.

    Uses Alembic when a script directory is present; otherwise falls back to
    metadata.create_all for dev/test.
    """
    from app.db import models  # noqa: F401 — register models on metadata

    engine = get_engine()
    alembic_ini = Path(__file__).parent.parent.parent / "alembic.ini"
    if alembic_ini.exists():
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", sqlite_url())
        command.upgrade(cfg, "head")
    else:
        Base.metadata.create_all(engine)

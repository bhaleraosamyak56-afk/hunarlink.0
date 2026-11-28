"""Synchronous SQLAlchemy 2.x database session and engine factory."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    cfg = settings or get_settings()
    url = cfg.database_url or cfg.build_mysql_url()
    connect_args = {}
    if isinstance(url, str) and url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_db_engine()
        try:
            from app.modules.auth.role_views import ensure_login_tracking_and_views

            ensure_login_tracking_and_views(_engine)
        except Exception:
            pass
        _session_factory = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()

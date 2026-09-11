from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def configure_sqlite(engine: AsyncEngine) -> None:
    """Fix pysqlite/aiosqlite's implicit-transaction handling, which otherwise
    silently conflicts with SQLAlchemy's own explicit BEGIN/SAVEPOINT
    management - e.g. it breaks the rollback-per-test fixture in
    tests/conftest.py, since Python's sqlite3-style driver auto-commits
    behind SQLAlchemy's back unless told not to. This is SQLAlchemy's own
    documented fix ("Pysqlite" driver docs, "Serializable isolation /
    Savepoints / Transactional DDL"), not specific to this project. Also
    turns on foreign-key enforcement and WAL mode, both off by default.
    """
    if engine.url.get_backend_name() != "sqlite":
        return

    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "connect")
    def _do_connect(dbapi_connection: Any, connection_record: Any) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @event.listens_for(sync_engine, "begin")
    def _do_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")


engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    connect_args=settings.asyncpg_connect_args,
)
configure_sqlite(engine)

SessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db

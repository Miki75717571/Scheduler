from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import configure_sqlite, get_db
from app.main import app
from app.models import (  # noqa: F401  registers tables on Base.metadata
    assignment,
    audit_log,
    availability,
    employee_score,
    invitation,
    rule,
    schedule_period,
    score_criterion,
    shift_slot,
    shift_type,
    user,
)

# NullPool: every connection is opened fresh and never reused across tests, so
# there's no pooled-connection/event-loop mismatch to worry about (see the
# asyncio_default_fixture_loop_scope note in pyproject.toml) and no risk of a
# stale connection surviving between an app-side pooler like Supabase's and us.
engine = create_async_engine(
    settings.async_test_database_url,
    connect_args=settings.test_asyncpg_connect_args,
    poolclass=NullPool,
)
configure_sqlite(engine)
TestingSessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """A session bound to a SAVEPOINT that's rolled back after the test, so
    that app code calling `db.commit()` (as the auth/invitation services do)
    doesn't leak data between tests. See SQLAlchemy's "Joining a Session into
    an External Transaction" docs for why `join_transaction_mode` is needed
    here instead of a plain `session.commit()` no-op.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, entry: AuditLog) -> AuditLog:
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_by_period(
        self, period_id: uuid.UUID, *, since: datetime | None = None
    ) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.period_id == period_id)
        if since is not None:
            stmt = stmt.where(AuditLog.at > since)
        stmt = stmt.order_by(AuditLog.at.desc())
        result = await self._db.execute(stmt)
        return list(result.scalars())

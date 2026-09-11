import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class StrEnumType(TypeDecorator[enum.Enum]):
    """Stores a Python (Str)Enum as plain VARCHAR - portable across every
    dialect, unlike sqlalchemy.Enum's native ENUM on Postgres (which SQLite
    has no equivalent for). Pair each use with a CheckConstraint on the
    column (see models/user.py) so invalid values are still rejected at the
    DB level, not just by the ORM.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type[enum.Enum], length: int, **kwargs: Any) -> None:
        super().__init__(length=length, **kwargs)
        self._enum_cls = enum_cls

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return value.value if isinstance(value, enum.Enum) else str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> enum.Enum | None:
        if value is None:
            return None
        return self._enum_cls(value)


class UTCDateTime(TypeDecorator[datetime]):
    """DateTime(timezone=True) that always round-trips as timezone-AWARE UTC,
    on every dialect. Postgres preserves tz-awareness natively; SQLite (and
    several other dialects) silently hand back a naive datetime on read,
    which breaks any `some_dt < datetime.now(UTC)` comparison - this bit
    services/invitation_service.py's expiry check on SQLite specifically.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to a UTCDateTime column - attach tzinfo first")
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

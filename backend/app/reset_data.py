"""Wipes demo/test data, keeping only the admin account(s) and real
configuration (CLAUDE.md JOB 7: "from now on this database holds real
people's data").

Deletes every User except role=ADMIN, and every Assignment, ScheduleRun,
Availability, AvailabilitySubmission, ShiftSlot, SchedulePeriod,
EmployeeScore, AuditLog, and Invitation row. Leaves ShiftType (+ per-weekday
overrides), Rule, ScoreCriterion, and SolverWeightConfig untouched - that's
real, ongoing configuration, not demo data.

Deliberately NOT part of start.ps1 or any other automatic flow - this is a
one-time, hand-run reset before inviting real people, or an explicit
"start over" during setup. Requires `--yes`; refuses to run without it.

Usage:
    uv run python -m app.reset_data --yes
"""

import argparse
import asyncio

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.availability import Availability, AvailabilitySubmission
from app.models.employee_score import EmployeeScore
from app.models.invitation import Invitation
from app.models.schedule_period import SchedulePeriod
from app.models.schedule_run import ScheduleRun
from app.models.shift_slot import ShiftSlot
from app.models.user import Role, User

# FK-safe order: children before the parents they reference.
_TABLES_IN_DELETE_ORDER = (
    Assignment,
    AuditLog,
    ScheduleRun,
    Availability,
    AvailabilitySubmission,
    ShiftSlot,
    SchedulePeriod,
    EmployeeScore,
    Invitation,
)


async def run() -> None:
    async with SessionLocal() as db:
        for model in _TABLES_IN_DELETE_ORDER:
            count = (await db.execute(select(func.count()).select_from(model))).scalar_one()
            await db.execute(delete(model))
            print(f"Deleted {count} row(s) from {model.__tablename__}.")

        non_admin_count = (
            await db.execute(select(func.count()).select_from(User).where(User.role != Role.ADMIN))
        ).scalar_one()
        await db.execute(delete(User).where(User.role != Role.ADMIN))
        print(f"Deleted {non_admin_count} non-admin user(s).")

        await db.commit()

    print(
        "\nDone. ShiftType/overrides, Rule, ScoreCriterion, and SolverWeightConfig rows"
        " were left untouched (real configuration, not demo data)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required. Confirms you want to permanently delete all non-admin users and "
        "all availability/assignments/periods/scores/runs data.",
    )
    args = parser.parse_args()

    if not args.yes:
        print(
            "Refusing to run without --yes. This permanently deletes all non-admin users "
            "and all availability/assignments/periods/scores/runs. Re-run as:\n"
            "  uv run python -m app.reset_data --yes"
        )
        raise SystemExit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()

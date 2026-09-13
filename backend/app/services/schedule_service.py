import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.availability import AvailabilityStatus
from app.models.rule import Rule, RulePhase, RuleScope
from app.models.schedule_period import PeriodState, SchedulePeriod
from app.models.shift_slot import ShiftSlot
from app.models.shift_type import ShiftType
from app.models.shift_type_weekday_override import ShiftTypeWeekdayOverride
from app.models.user import Role, User
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.rule_repository import RuleRepository
from app.repositories.shift_slot_repository import ShiftSlotRepository
from app.repositories.shift_type_repository import ShiftTypeRepository
from app.repositories.user_repository import UserRepository
from app.rules.schedule_validator import (
    check_unavailable_assignments,
    check_understaffing,
    evaluate_schedule_rules,
)
from app.rules.types import AssignedShift, ScheduleViolation, SlotStaffing, UserScheduleContext
from app.rules.weekdays import Weekday, is_weekend
from app.schemas.assignment import AssignmentCreate, BulkAssignmentOp
from app.services.shift_effective import overrides_by_weekday_for, resolve_effective_config


class AssignmentError(Exception):
    def __init__(self, message_key: str, params: dict[str, Any] | None = None) -> None:
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)


def _snapshot(assignment: Assignment) -> dict[str, Any]:
    return {
        "shift_slot_id": str(assignment.shift_slot_id),
        "user_id": str(assignment.user_id),
        "source": assignment.source.value,
        "is_locked": assignment.is_locked,
    }


def _rule_applies_to(rule: Rule, user: User) -> bool:
    if rule.scope == RuleScope.GLOBAL:
        return True
    if rule.scope == RuleScope.USER:
        return rule.scope_ref == str(user.id)
    if rule.scope == RuleScope.EMPLOYMENT_TYPE:
        return user.employment_type is not None and rule.scope_ref == user.employment_type.value
    return False


@dataclass
class _PeriodData:
    slots: list[ShiftSlot]
    shift_types_by_id: dict[uuid.UUID, ShiftType]
    overrides_by_type: dict[uuid.UUID, dict[Weekday, ShiftTypeWeekdayOverride]]
    assignments: list[Assignment]
    active_users: list[User]
    availability_rows: list[tuple[uuid.UUID, uuid.UUID, AvailabilityStatus]]


class ScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._assignments = AssignmentRepository(db)
        self._slots = ShiftSlotRepository(db)
        self._shift_types = ShiftTypeRepository(db)
        self._users = UserRepository(db)
        self._availability = AvailabilityRepository(db)
        self._rules = RuleRepository(db)
        self._audit_log = AuditLogRepository(db)

    # --- shared loading -----------------------------------------------

    async def _load_period_data(self, period: SchedulePeriod) -> _PeriodData:
        slots = await self._slots.list_by_period(period.id)
        shift_types_by_id = {st.id: st for st in await self._shift_types.list_all()}
        overrides = await self._shift_types.list_overrides_for_types(shift_types_by_id.keys())
        overrides_rows_by_type: dict[uuid.UUID, list[ShiftTypeWeekdayOverride]] = defaultdict(list)
        for override in overrides:
            overrides_rows_by_type[override.shift_type_id].append(override)
        overrides_by_type = {
            type_id: overrides_by_weekday_for(rows)
            for type_id, rows in overrides_rows_by_type.items()
        }
        assignments = await self._assignments.list_by_period(period.id)
        active_users = [u for u in await self._users.list_all() if u.is_active]
        availability_rows = await self._availability.list_entries_for_slots([s.id for s in slots])
        return _PeriodData(
            slots=slots,
            shift_types_by_id=shift_types_by_id,
            overrides_by_type=overrides_by_type,
            assignments=assignments,
            active_users=active_users,
            availability_rows=availability_rows,
        )

    def _to_assigned_shift(
        self,
        slot: ShiftSlot,
        shift_types_by_id: dict[uuid.UUID, ShiftType],
        overrides_by_type: dict[uuid.UUID, dict[Weekday, ShiftTypeWeekdayOverride]],
    ) -> AssignedShift:
        shift_type = shift_types_by_id[slot.shift_type_id]
        effective = resolve_effective_config(
            shift_type, overrides_by_type.get(shift_type.id, {}), slot.date
        )
        return AssignedShift(
            shift_slot_id=slot.id,
            date=slot.date,
            shift_type_code=shift_type.code,
            start_time=effective.start_time,
            end_time=effective.end_time,
            is_weekend=is_weekend(slot.date),
        )

    def _assigned_shifts_by_user(self, data: _PeriodData) -> dict[uuid.UUID, list[AssignedShift]]:
        slots_by_id = {s.id: s for s in data.slots}
        by_user: dict[uuid.UUID, list[AssignedShift]] = defaultdict(list)
        for assignment in data.assignments:
            slot = slots_by_id.get(assignment.shift_slot_id)
            if slot is None:
                continue
            by_user[assignment.user_id].append(
                self._to_assigned_shift(slot, data.shift_types_by_id, data.overrides_by_type)
            )
        return by_user

    # --- violations ------------------------------------------------------

    async def compute_violations(self, period: SchedulePeriod) -> list[ScheduleViolation]:
        data = await self._load_period_data(period)
        assigned_by_user = self._assigned_shifts_by_user(data)
        schedule_rules = await self._rules.list_active_by_phase(RulePhase.SCHEDULE)

        violations: list[ScheduleViolation] = []
        for user in data.active_users:
            applicable = [r for r in schedule_rules if _rule_applies_to(r, user)]
            context = UserScheduleContext(
                user_id=user.id,
                assigned_shifts=tuple(
                    sorted(assigned_by_user.get(user.id, []), key=lambda s: (s.date, s.start_time))
                ),
                contract_min_shifts=user.contract_min_shifts,
                contract_max_shifts=user.contract_max_shifts,
            )
            violations.extend(evaluate_schedule_rules(applicable, context))

        assigned_user_ids_by_slot: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for assignment in data.assignments:
            assigned_user_ids_by_slot[assignment.shift_slot_id].append(assignment.user_id)
        slot_staffing = [
            SlotStaffing(
                shift_slot_id=slot.id,
                date=slot.date,
                shift_type_code=data.shift_types_by_id[slot.shift_type_id].code,
                required_staff=slot.required_staff,
                min_staff=slot.min_staff,
                max_staff=slot.max_staff,
                is_closed=slot.is_closed,
                assigned_user_ids=tuple(assigned_user_ids_by_slot.get(slot.id, [])),
            )
            for slot in data.slots
        ]
        violations.extend(check_understaffing(slot_staffing))

        declared_available = {(row[0], row[1]) for row in data.availability_rows}
        violations.extend(
            check_unavailable_assignments(
                {uid: tuple(shifts) for uid, shifts in assigned_by_user.items()},
                declared_available,
            )
        )
        return violations

    # --- reads -------------------------------------------------------

    async def list_visible_assignments(
        self, period: SchedulePeriod, viewer: User, *, filter_user_id: uuid.UUID | None = None
    ) -> list[Assignment]:
        if viewer.role in (Role.MANAGER, Role.ADMIN):
            assignments = await self._assignments.list_by_period(period.id)
            if filter_user_id is not None:
                assignments = [a for a in assignments if a.user_id == filter_user_id]
            return assignments

        if period.state != PeriodState.PUBLISHED:
            raise AssignmentError("assignment.period_not_published")
        own = await self._assignments.list_by_user_and_period(viewer.id, period.id)
        own_slot_ids = {a.shift_slot_id for a in own}
        return await self._assignments.list_by_slots(own_slot_ids)

    async def list_audit_log(
        self, period: SchedulePeriod, *, since_publish_only: bool = False
    ) -> list[AuditLog]:
        since = period.published_at if since_publish_only else None
        return await self._audit_log.list_by_period(period.id, since=since)

    async def available_employees(
        self, period: SchedulePeriod, slot_id: uuid.UUID
    ) -> list[tuple[User, AvailabilityStatus]]:
        slot = await self._slots.get_by_id(slot_id)
        if slot is None or slot.period_id != period.id:
            raise AssignmentError("assignment.slot_not_found")
        if slot.is_closed:
            return []

        data = await self._load_period_data(period)
        candidate_slot_shift = self._to_assigned_shift(
            slot, data.shift_types_by_id, data.overrides_by_type
        )
        assigned_by_user = self._assigned_shifts_by_user(data)
        users_by_id = {u.id: u for u in data.active_users}
        schedule_rules = await self._rules.list_active_by_phase(RulePhase.SCHEDULE)

        candidates: list[tuple[User, AvailabilityStatus]] = []
        for user_id, target_slot_id, status in data.availability_rows:
            if target_slot_id != slot_id:
                continue
            user = users_by_id.get(user_id)
            if user is None:
                continue

            applicable = [r for r in schedule_rules if _rule_applies_to(r, user)]
            existing_shifts = assigned_by_user.get(user.id, [])
            baseline = UserScheduleContext(
                user_id=user.id,
                assigned_shifts=tuple(existing_shifts),
                contract_min_shifts=user.contract_min_shifts,
                contract_max_shifts=user.contract_max_shifts,
            )
            hypothetical = UserScheduleContext(
                user_id=user.id,
                assigned_shifts=tuple([*existing_shifts, candidate_slot_shift]),
                contract_min_shifts=user.contract_min_shifts,
                contract_max_shifts=user.contract_max_shifts,
            )
            baseline_errors = sum(
                1 for v in evaluate_schedule_rules(applicable, baseline) if v.severity == "ERROR"
            )
            hypothetical_errors = sum(
                1
                for v in evaluate_schedule_rules(applicable, hypothetical)
                if v.severity == "ERROR"
            )
            if hypothetical_errors > baseline_errors:
                continue  # a HARD rule would newly break - excluded, per spec

            candidates.append((user, status))
        return candidates

    # --- mutations (single) -------------------------------------------

    async def create_assignment(
        self, period: SchedulePeriod, payload: AssignmentCreate, *, actor: User
    ) -> Assignment:
        assignment = await self._create(period, payload, actor=actor)
        await self._db.commit()
        await self._db.refresh(assignment)
        return assignment

    async def remove_assignment(
        self, period: SchedulePeriod, assignment_id: uuid.UUID, *, actor: User
    ) -> None:
        await self._remove(period, assignment_id, actor=actor)
        await self._db.commit()

    async def move_assignment(
        self,
        period: SchedulePeriod,
        assignment_id: uuid.UUID,
        target_slot_id: uuid.UUID,
        *,
        actor: User,
    ) -> Assignment:
        assignment = await self._move(period, assignment_id, target_slot_id, actor=actor)
        await self._db.commit()
        await self._db.refresh(assignment)
        return assignment

    async def set_lock(
        self, period: SchedulePeriod, assignment_id: uuid.UUID, is_locked: bool, *, actor: User
    ) -> Assignment:
        assignment = await self._lock(period, assignment_id, is_locked, actor=actor)
        await self._db.commit()
        await self._db.refresh(assignment)
        return assignment

    async def bulk(
        self, period: SchedulePeriod, operations: list[BulkAssignmentOp], *, actor: User
    ) -> list[Assignment]:
        touched: list[Assignment] = []
        for op in operations:
            if op.op == "add":
                if op.shift_slot_id is None or op.user_id is None:
                    raise AssignmentError("assignment.invalid_bulk_operation", {"op": op.op})
                touched.append(
                    await self._create(
                        period,
                        AssignmentCreate(
                            shift_slot_id=op.shift_slot_id,
                            user_id=op.user_id,
                            source=op.source,
                            is_locked=bool(op.is_locked),
                        ),
                        actor=actor,
                    )
                )
            elif op.op == "remove":
                if op.assignment_id is None:
                    raise AssignmentError("assignment.invalid_bulk_operation", {"op": op.op})
                await self._remove(period, op.assignment_id, actor=actor)
            elif op.op == "move":
                if op.assignment_id is None or op.shift_slot_id is None:
                    raise AssignmentError("assignment.invalid_bulk_operation", {"op": op.op})
                touched.append(
                    await self._move(period, op.assignment_id, op.shift_slot_id, actor=actor)
                )
            elif op.op == "lock":
                if op.assignment_id is None or op.is_locked is None:
                    raise AssignmentError("assignment.invalid_bulk_operation", {"op": op.op})
                touched.append(
                    await self._lock(period, op.assignment_id, op.is_locked, actor=actor)
                )
            else:  # pragma: no cover - BulkOpType already constrains this
                raise AssignmentError("assignment.invalid_bulk_operation", {"op": op.op})

        await self._db.commit()
        for assignment in touched:
            await self._db.refresh(assignment)
        return touched

    # --- mutations (no-commit core, reused by bulk) --------------------

    async def _get_owned_slot(self, period: SchedulePeriod, shift_slot_id: uuid.UUID) -> ShiftSlot:
        slot = await self._slots.get_by_id(shift_slot_id)
        if slot is None or slot.period_id != period.id:
            raise AssignmentError("assignment.slot_not_found")
        return slot

    async def _get_owned_assignment(
        self, period: SchedulePeriod, assignment_id: uuid.UUID
    ) -> Assignment:
        assignment = await self._assignments.get_by_id(assignment_id)
        if assignment is None:
            raise AssignmentError("assignment.not_found")
        slot = await self._slots.get_by_id(assignment.shift_slot_id)
        if slot is None or slot.period_id != period.id:
            raise AssignmentError("assignment.not_found")
        return assignment

    async def _audit(
        self,
        period: SchedulePeriod,
        actor: User,
        *,
        action: str,
        entity_id: uuid.UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        await self._audit_log.create(
            AuditLog(
                actor_user_id=actor.id,
                period_id=period.id,
                action=action,
                entity_type="Assignment",
                entity_id=entity_id,
                before=before,
                after=after,
            )
        )

    async def _create(
        self, period: SchedulePeriod, payload: AssignmentCreate, *, actor: User
    ) -> Assignment:
        slot = await self._get_owned_slot(period, payload.shift_slot_id)
        if slot.is_closed:
            raise AssignmentError("assignment.slot_closed")

        target_user = await self._users.get_by_id(payload.user_id)
        if target_user is None:
            raise AssignmentError("assignment.user_not_found")
        if not target_user.is_active:
            raise AssignmentError("assignment.user_inactive")

        if await self._assignments.get_by_slot_and_user(slot.id, target_user.id) is not None:
            raise AssignmentError("assignment.already_exists")

        assignment = Assignment(
            shift_slot_id=slot.id,
            user_id=target_user.id,
            source=payload.source,
            is_locked=payload.is_locked,
            created_by_user_id=actor.id,
            modified_after_publish=period.state == PeriodState.PUBLISHED,
        )
        await self._assignments.create(assignment)
        await self._audit(
            period,
            actor,
            action="assignment.create",
            entity_id=assignment.id,
            before=None,
            after=_snapshot(assignment),
        )
        return assignment

    async def _remove(
        self, period: SchedulePeriod, assignment_id: uuid.UUID, *, actor: User
    ) -> None:
        assignment = await self._get_owned_assignment(period, assignment_id)
        before = _snapshot(assignment)
        await self._assignments.delete(assignment)
        await self._audit(
            period,
            actor,
            action="assignment.remove",
            entity_id=assignment_id,
            before=before,
            after=None,
        )

    async def _move(
        self,
        period: SchedulePeriod,
        assignment_id: uuid.UUID,
        target_slot_id: uuid.UUID,
        *,
        actor: User,
    ) -> Assignment:
        assignment = await self._get_owned_assignment(period, assignment_id)
        target_slot = await self._get_owned_slot(period, target_slot_id)
        if target_slot.is_closed:
            raise AssignmentError("assignment.slot_closed")
        if target_slot.id != assignment.shift_slot_id:
            existing = await self._assignments.get_by_slot_and_user(
                target_slot.id, assignment.user_id
            )
            if existing is not None:
                raise AssignmentError("assignment.already_exists")

        before = _snapshot(assignment)
        assignment.shift_slot_id = target_slot.id
        assignment.updated_at = datetime.now(UTC)
        if period.state == PeriodState.PUBLISHED:
            assignment.modified_after_publish = True
        await self._assignments.save(assignment)
        await self._audit(
            period,
            actor,
            action="assignment.move",
            entity_id=assignment.id,
            before=before,
            after=_snapshot(assignment),
        )
        return assignment

    async def _lock(
        self, period: SchedulePeriod, assignment_id: uuid.UUID, is_locked: bool, *, actor: User
    ) -> Assignment:
        assignment = await self._get_owned_assignment(period, assignment_id)
        before = _snapshot(assignment)
        assignment.is_locked = is_locked
        assignment.updated_at = datetime.now(UTC)
        await self._assignments.save(assignment)
        await self._audit(
            period,
            actor,
            action="assignment.lock" if is_locked else "assignment.unlock",
            entity_id=assignment.id,
            before=before,
            after=_snapshot(assignment),
        )
        return assignment

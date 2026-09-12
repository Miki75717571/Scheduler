import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.assignment import AssignmentSource
from app.models.availability import AvailabilityStatus


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_slot_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    source: AssignmentSource
    is_locked: bool
    modified_after_publish: bool
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None


class AssignmentCreate(BaseModel):
    shift_slot_id: uuid.UUID
    user_id: uuid.UUID
    source: AssignmentSource = AssignmentSource.MANUAL
    is_locked: bool = False


class AssignmentMove(BaseModel):
    shift_slot_id: uuid.UUID


class AssignmentLockUpdate(BaseModel):
    is_locked: bool


class ScheduleViolationRead(BaseModel):
    severity: str
    rule_code: str
    rule_type: str
    message_key: str
    message_params: dict[str, Any]
    shift_slot_id: uuid.UUID | None
    user_id: uuid.UUID | None


class AssignmentMutationResult(BaseModel):
    assignment: AssignmentRead | None
    violations: list[ScheduleViolationRead]


BulkOpType = Literal["add", "remove", "move", "lock"]


class BulkAssignmentOp(BaseModel):
    """One entry of a bulk request. Field requirements depend on `op`:
    add needs shift_slot_id + user_id; remove/move/lock need assignment_id
    (move also needs shift_slot_id as the target, lock also needs is_locked).
    """

    op: BulkOpType
    assignment_id: uuid.UUID | None = None
    shift_slot_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    source: AssignmentSource = AssignmentSource.MANUAL
    is_locked: bool | None = None


class BulkAssignmentRequest(BaseModel):
    operations: list[BulkAssignmentOp] = Field(min_length=1)


class BulkAssignmentResult(BaseModel):
    assignments: list[AssignmentRead]
    violations: list[ScheduleViolationRead]


class AvailableEmployeeRead(BaseModel):
    user_id: uuid.UUID
    full_name: str
    status: AvailabilityStatus


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID
    period_id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    at: datetime

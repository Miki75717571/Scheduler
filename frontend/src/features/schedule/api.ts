import { apiClient } from "../../api/client";
import type {
  Assignment,
  AssignmentMutationResult,
  AvailableEmployee,
  ScheduleViolation,
} from "../../api/types";

export function fetchAssignments(periodId: string): Promise<Assignment[]> {
  return apiClient.get<Assignment[]>(`/periods/${periodId}/assignments`);
}

export function fetchViolations(periodId: string): Promise<ScheduleViolation[]> {
  return apiClient.get<ScheduleViolation[]>(`/periods/${periodId}/violations`);
}

export function fetchAvailableEmployees(
  periodId: string,
  slotId: string,
): Promise<AvailableEmployee[]> {
  return apiClient.get<AvailableEmployee[]>(
    `/periods/${periodId}/slots/${slotId}/available-employees`,
  );
}

export function createAssignment(
  periodId: string,
  payload: { shift_slot_id: string; user_id: string; is_locked?: boolean },
): Promise<AssignmentMutationResult> {
  return apiClient.post<AssignmentMutationResult>(`/periods/${periodId}/assignments`, payload);
}

export function removeAssignment(
  periodId: string,
  assignmentId: string,
): Promise<AssignmentMutationResult> {
  return apiClient.delete<AssignmentMutationResult>(
    `/periods/${periodId}/assignments/${assignmentId}`,
  );
}

export function moveAssignment(
  periodId: string,
  assignmentId: string,
  targetShiftSlotId: string,
): Promise<AssignmentMutationResult> {
  return apiClient.patch<AssignmentMutationResult>(
    `/periods/${periodId}/assignments/${assignmentId}/move`,
    { shift_slot_id: targetShiftSlotId },
  );
}

export function setAssignmentLock(
  periodId: string,
  assignmentId: string,
  isLocked: boolean,
): Promise<Assignment> {
  return apiClient.patch<Assignment>(`/periods/${periodId}/assignments/${assignmentId}/lock`, {
    is_locked: isLocked,
  });
}

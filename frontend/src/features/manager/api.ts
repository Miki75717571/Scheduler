import { apiClient } from "../../api/client";
import type {
  AvailabilitySubmission,
  PeriodState,
  SchedulePeriod,
  ShiftSlot,
  SubmissionTrackerEntry,
} from "../../api/types";

export function fetchPeriods(): Promise<SchedulePeriod[]> {
  return apiClient.get<SchedulePeriod[]>("/periods");
}

export function fetchPeriod(periodId: string): Promise<SchedulePeriod> {
  return apiClient.get<SchedulePeriod>(`/periods/${periodId}`);
}

export function createPeriod(payload: {
  year: number;
  month: number;
  availability_deadline: string | null;
}): Promise<SchedulePeriod> {
  return apiClient.post<SchedulePeriod>("/periods", payload);
}

export function updatePeriodState(
  periodId: string,
  state: PeriodState,
  overrideViolations = false,
): Promise<SchedulePeriod> {
  return apiClient.patch<SchedulePeriod>(`/periods/${periodId}/state`, {
    state,
    override_violations: overrideViolations,
  });
}

export function fetchSlots(periodId: string): Promise<ShiftSlot[]> {
  return apiClient.get<ShiftSlot[]>(`/periods/${periodId}/slots`);
}

export function updateSlot(
  periodId: string,
  slotId: string,
  payload: Partial<Pick<ShiftSlot, "required_staff" | "min_staff" | "max_staff" | "is_closed" | "note">>,
): Promise<ShiftSlot> {
  return apiClient.patch<ShiftSlot>(`/periods/${periodId}/slots/${slotId}`, payload);
}

export function fetchTracker(periodId: string): Promise<SubmissionTrackerEntry[]> {
  return apiClient.get<SubmissionTrackerEntry[]>(`/periods/${periodId}/availability/tracker`);
}

export function reopenAvailability(
  periodId: string,
  userId: string,
): Promise<AvailabilitySubmission> {
  return apiClient.post<AvailabilitySubmission>(
    `/periods/${periodId}/availability/${userId}/reopen`,
  );
}

export function revokeReopenAvailability(
  periodId: string,
  userId: string,
): Promise<AvailabilitySubmission> {
  return apiClient.delete<AvailabilitySubmission>(
    `/periods/${periodId}/availability/${userId}/reopen`,
  );
}

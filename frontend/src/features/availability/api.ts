import { apiClient } from "../../api/client";
import type {
  AvailabilityDetail,
  AvailabilityStatus,
  SchedulePeriod,
  ShiftSlot,
  ShiftType,
} from "../../api/types";

export function fetchPeriods(): Promise<SchedulePeriod[]> {
  return apiClient.get<SchedulePeriod[]>("/periods");
}

export function fetchShiftTypes(): Promise<ShiftType[]> {
  return apiClient.get<ShiftType[]>("/shift-types");
}

export function fetchSlots(periodId: string): Promise<ShiftSlot[]> {
  return apiClient.get<ShiftSlot[]>(`/periods/${periodId}/slots`);
}

export function fetchAvailability(periodId: string, userId: string): Promise<AvailabilityDetail> {
  return apiClient.get<AvailabilityDetail>(`/periods/${periodId}/availability/${userId}`);
}

export function writeAvailability(
  periodId: string,
  userId: string,
  entries: { shift_slot_id: string; status: AvailabilityStatus }[],
): Promise<AvailabilityDetail> {
  return apiClient.put<AvailabilityDetail>(`/periods/${periodId}/availability/${userId}`, {
    entries,
  });
}

export function submitAvailability(periodId: string, userId: string): Promise<AvailabilityDetail> {
  return apiClient.post<AvailabilityDetail>(`/periods/${periodId}/availability/${userId}/submit`);
}

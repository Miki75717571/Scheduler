import type { AvailabilityStatus, ShiftSlot, ShiftType } from "../../api/types";
import { isWeekend, weekdayCodeOf } from "../../lib/weekdays";

// Deliberately data-driven, never hard-coded on a shift type's code: "morning"
// is "the earliest-starting open shift that day", "evening" is "the
// latest-starting one" - so a renamed/reordered ShiftType never breaks these
// (CLAUDE.md: shift structure lives in data, not in scattered `if`s).

function groupByDate(slots: ShiftSlot[]): Record<string, ShiftSlot[]> {
  const byDate: Record<string, ShiftSlot[]> = {};
  for (const slot of slots) {
    (byDate[slot.date] ??= []).push(slot);
  }
  return byDate;
}

function extremeStartTimeSlot(
  slots: ShiftSlot[],
  shiftTypesById: Record<string, ShiftType>,
  pick: "earliest" | "latest",
): ShiftSlot {
  return slots.reduce((chosen, slot) => {
    const chosenTime = shiftTypesById[chosen.shift_type_id].start_time;
    const slotTime = shiftTypesById[slot.shift_type_id].start_time;
    const better = pick === "earliest" ? slotTime < chosenTime : slotTime > chosenTime;
    return better ? slot : chosen;
  });
}

export function allMorningsPatch(
  slots: ShiftSlot[],
  shiftTypesById: Record<string, ShiftType>,
): Record<string, AvailabilityStatus> {
  const patch: Record<string, AvailabilityStatus> = {};
  for (const daySlots of Object.values(groupByDate(slots))) {
    const open = daySlots.filter((s) => !s.is_closed);
    if (open.length === 0) continue;
    patch[extremeStartTimeSlot(open, shiftTypesById, "earliest").id] = "AVAILABLE";
  }
  return patch;
}

export function allWeekdayEveningsPatch(
  slots: ShiftSlot[],
  shiftTypesById: Record<string, ShiftType>,
): Record<string, AvailabilityStatus> {
  const patch: Record<string, AvailabilityStatus> = {};
  for (const [date, daySlots] of Object.entries(groupByDate(slots))) {
    if (isWeekend(weekdayCodeOf(date))) continue;
    const open = daySlots.filter((s) => !s.is_closed);
    if (open.length === 0) continue;
    patch[extremeStartTimeSlot(open, shiftTypesById, "latest").id] = "AVAILABLE";
  }
  return patch;
}

export function allWeekendsPatch(slots: ShiftSlot[]): Record<string, AvailabilityStatus> {
  const patch: Record<string, AvailabilityStatus> = {};
  for (const slot of slots) {
    if (slot.is_closed) continue;
    if (isWeekend(weekdayCodeOf(slot.date))) patch[slot.id] = "AVAILABLE";
  }
  return patch;
}

export function clearAllPatch(slots: ShiftSlot[]): Record<string, AvailabilityStatus> {
  const patch: Record<string, AvailabilityStatus> = {};
  for (const slot of slots) {
    patch[slot.id] = "UNAVAILABLE";
  }
  return patch;
}

/**
 * "Copy from last month": matches slots by (weekday, shift_type_id) - the
 * same ShiftType row is reused across periods, only ShiftSlot is
 * per-period, so this is a stable join, not a guess by date or code. When a
 * weekday/shift combination was marked PREFERRED more often than AVAILABLE
 * last month, it's carried over as PREFERRED; otherwise AVAILABLE.
 */
export function copyFromLastMonthPatch(
  currentSlots: ShiftSlot[],
  previousSlots: ShiftSlot[],
  previousStatusBySlotId: Record<string, AvailabilityStatus>,
): Record<string, AvailabilityStatus> {
  const tally: Record<string, { AVAILABLE: number; PREFERRED: number }> = {};
  for (const slot of previousSlots) {
    const status = previousStatusBySlotId[slot.id];
    if (status === undefined || status === "UNAVAILABLE") continue;
    const key = `${weekdayCodeOf(slot.date)}|${slot.shift_type_id}`;
    tally[key] ??= { AVAILABLE: 0, PREFERRED: 0 };
    tally[key][status] += 1;
  }

  const patch: Record<string, AvailabilityStatus> = {};
  for (const slot of currentSlots) {
    if (slot.is_closed) continue;
    const key = `${weekdayCodeOf(slot.date)}|${slot.shift_type_id}`;
    const counts = tally[key];
    if (!counts) continue;
    patch[slot.id] = counts.PREFERRED >= counts.AVAILABLE && counts.PREFERRED > 0 ? "PREFERRED" : "AVAILABLE";
  }
  return patch;
}

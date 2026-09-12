import type { ScheduleViolation, ShiftSlot } from "../../api/types";

export type SlotStatus = "green" | "amber" | "red" | "closed";

// Distinguishable without colour alone (CLAUDE.md i18n/accessibility
// discipline mirrored from features/availability/chip.ts): every status also
// gets its own glyph, used both as a small badge on the lane and in the
// aria-label read out by a screen reader.
export const SLOT_STATUS_ICON: Record<SlotStatus, string> = {
  green: "✓",
  amber: "⚠",
  red: "✕",
  closed: "⛔",
};

export const SLOT_STATUS_STYLE: Record<SlotStatus, string> = {
  green: "border-emerald-400 bg-emerald-50",
  amber: "border-amber-400 bg-amber-50",
  red: "border-2 border-red-500 bg-red-50",
  closed: "border-dashed border-slate-300 bg-slate-50",
};

// A violation "belongs" to a slot if it names the slot directly, or - for the
// handful of rule types that record shift_slot_id=null because they span
// multiple slots (ONE_SHIFT_PER_DAY, MIN_REST_HOURS) - if the slot shows up
// in one of their per-shift param fields. Mirrors the shapes produced by
// backend/app/rules/schedule_validator.py's message_params.
function violationTouchesSlot(v: ScheduleViolation, slotId: string): boolean {
  if (v.shift_slot_id === slotId) return true;
  const params = v.message_params;
  const ids = params.shift_slot_ids;
  if (Array.isArray(ids) && ids.includes(slotId)) return true;
  if (params.from_shift_slot_id === slotId || params.to_shift_slot_id === slotId) return true;
  return false;
}

export function violationsForSlot(
  slotId: string,
  violations: ScheduleViolation[],
): ScheduleViolation[] {
  return violations.filter((v) => violationTouchesSlot(v, slotId));
}

// Colour policy per ARCHITECTURE.md ss6: green = fully staffed and legal,
// amber = below target but legal, red = below minimum staff or a rule
// violation. A closed day/shift is neither - it opts out of staffing
// entirely (mirrors schedule_validator.check_understaffing skipping closed
// slots).
export function computeSlotStatus(
  slot: Pick<ShiftSlot, "is_closed" | "min_staff" | "required_staff">,
  assignedCount: number,
  slotViolations: ScheduleViolation[],
): SlotStatus {
  if (slot.is_closed) return "closed";

  const hasError = slotViolations.some((v) => v.severity === "ERROR");
  if (hasError || assignedCount < slot.min_staff) return "red";

  const hasWarning = slotViolations.some((v) => v.severity === "WARNING");
  if (hasWarning || assignedCount < slot.required_staff) return "amber";

  return "green";
}

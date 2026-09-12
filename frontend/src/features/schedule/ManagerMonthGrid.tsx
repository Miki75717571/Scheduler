import { useTranslation } from "react-i18next";

import type { Assignment, ScheduleViolation, ShiftSlot, ShiftType } from "../../api/types";
import { cn } from "../../lib/utils";
import { WEEKDAY_CODES, parseIsoDate } from "../../lib/weekdays";
import { violationsForSlot } from "./colorLogic";
import { monthWeeks } from "./monthGrid";
import { ShiftLane } from "./ShiftLane";

interface DragPayload {
  assignmentId: string;
  sourceSlotId: string;
}

interface ManagerMonthGridProps {
  year: number;
  month: number;
  slots: ShiftSlot[];
  shiftTypes: ShiftType[];
  assignments: Assignment[];
  violations: ScheduleViolation[];
  selectedEmployeeId: string | null;
  highlightedDate: string | null;
  onAddClick: (slot: ShiftSlot) => void;
  onToggleLock: (assignment: Assignment) => void;
  onRemove: (assignment: Assignment) => void;
  onMove: (assignmentId: string, targetSlotId: string) => void;
}

export function ManagerMonthGrid({
  year,
  month,
  slots,
  shiftTypes,
  assignments,
  violations,
  selectedEmployeeId,
  highlightedDate,
  onAddClick,
  onToggleLock,
  onRemove,
  onMove,
}: ManagerMonthGridProps) {
  const { t, i18n } = useTranslation();

  const shiftTypesById = Object.fromEntries(shiftTypes.map((st) => [st.id, st]));

  const slotsByDate: Record<string, ShiftSlot[]> = {};
  for (const slot of slots) {
    (slotsByDate[slot.date] ??= []).push(slot);
  }
  for (const date of Object.keys(slotsByDate)) {
    slotsByDate[date].sort(
      (a, b) => shiftTypesById[a.shift_type_id].sort_order - shiftTypesById[b.shift_type_id].sort_order,
    );
  }

  const assignmentsBySlot: Record<string, Assignment[]> = {};
  for (const assignment of assignments) {
    (assignmentsBySlot[assignment.shift_slot_id] ??= []).push(assignment);
  }

  const weeks = monthWeeks(year, month);

  if (slots.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("schedule.noSlots")}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[880px] grid-cols-7 gap-1 print:min-w-0 print:gap-0.5">
        {WEEKDAY_CODES.map((code) => (
          <div key={code} className="px-1 pb-1 text-center text-xs font-semibold text-muted-foreground">
            {t(`weekdaysShort.${code}`)}
          </div>
        ))}
        {weeks.map((week, weekIndex) =>
          week.map((date, dayIndex) => {
            if (!date) {
              return <div key={`${weekIndex}-${dayIndex}`} className="rounded border border-transparent" />;
            }
            const daySlots = slotsByDate[date] ?? [];
            return (
              <div
                key={date}
                id={`schedule-day-${date}`}
                className={cn(
                  "space-y-1 rounded border border-border p-1 print:break-inside-avoid",
                  highlightedDate === date && "ring-2 ring-sky-500",
                )}
              >
                <div className="text-right text-xs font-semibold text-muted-foreground">
                  {parseIsoDate(date).getDate()}
                </div>
                {daySlots.map((slot) => (
                  <ShiftLane
                    key={slot.id}
                    slot={slot}
                    shiftType={shiftTypesById[slot.shift_type_id]}
                    assignments={assignmentsBySlot[slot.id] ?? []}
                    slotViolations={violationsForSlot(slot.id, violations)}
                    selectedEmployeeId={selectedEmployeeId}
                    language={i18n.language}
                    onAdd={() => onAddClick(slot)}
                    onToggleLock={onToggleLock}
                    onRemove={onRemove}
                    onDropAssignment={(payload: DragPayload) => onMove(payload.assignmentId, slot.id)}
                  />
                ))}
              </div>
            );
          }),
        )}
      </div>
    </div>
  );
}

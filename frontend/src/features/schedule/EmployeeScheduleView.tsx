import { useTranslation } from "react-i18next";

import type { Assignment, ShiftSlot, ShiftType } from "../../api/types";
import { cn } from "../../lib/utils";
import { isWeekend, parseIsoDate, weekdayCodeOf } from "../../lib/weekdays";

interface EmployeeScheduleViewProps {
  ownUserId: string;
  slots: ShiftSlot[];
  shiftTypes: ShiftType[];
  assignments: Assignment[];
}

export function EmployeeScheduleView({
  ownUserId,
  slots,
  shiftTypes,
  assignments,
}: EmployeeScheduleViewProps) {
  const { t, i18n } = useTranslation();

  const slotsById = Object.fromEntries(slots.map((s) => [s.id, s]));
  const shiftTypesById = Object.fromEntries(shiftTypes.map((st) => [st.id, st]));

  const byUser: Record<string, number> = {};
  for (const a of assignments) byUser[a.user_id] = (byUser[a.user_id] ?? 0) + 1;
  const totalShifts = byUser[ownUserId] ?? 0;

  const assignmentsBySlot: Record<string, Assignment[]> = {};
  for (const a of assignments) (assignmentsBySlot[a.shift_slot_id] ??= []).push(a);

  const own = assignments
    .filter((a) => a.user_id === ownUserId)
    .map((a) => ({ assignment: a, slot: slotsById[a.shift_slot_id] }))
    .filter((entry): entry is { assignment: Assignment; slot: ShiftSlot } => Boolean(entry.slot))
    .sort((a, b) => {
      if (a.slot.date !== b.slot.date) return a.slot.date.localeCompare(b.slot.date);
      return (
        shiftTypesById[a.slot.shift_type_id].sort_order - shiftTypesById[b.slot.shift_type_id].sort_order
      );
    });

  const anyChanged = own.some((entry) => entry.assignment.modified_after_publish);

  if (own.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("employeeSchedule.noShifts")}</p>;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border bg-secondary px-3 py-2 text-sm font-medium">
        {t("employeeSchedule.totalShifts", { count: totalShifts })}
      </div>

      {anyChanged && (
        <div className="rounded-md border border-sky-300 bg-sky-50 px-3 py-2 text-sm text-sky-900">
          {t("employeeSchedule.changedNotice")}
        </div>
      )}

      <ul className="space-y-2">
        {own.map(({ assignment, slot }) => {
          const shiftType = shiftTypesById[slot.shift_type_id];
          const shiftName = i18n.language === "pl" ? shiftType.name_pl : shiftType.name_en;
          const weekday = weekdayCodeOf(slot.date);
          const colleagues = (assignmentsBySlot[slot.id] ?? []).filter((a) => a.user_id !== ownUserId);

          return (
            <li
              key={assignment.id}
              className={cn(
                "rounded-lg border-2 p-3",
                isWeekend(weekday) ? "border-slate-300 bg-slate-50" : "border-primary/30 bg-background",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">
                    {t(`weekdaysFull.${weekday}`)} {parseIsoDate(slot.date).getDate()} · {shiftName}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {shiftType.start_time.slice(0, 5)}–{shiftType.end_time.slice(0, 5)}
                  </p>
                </div>
                {assignment.modified_after_publish && (
                  <span className="shrink-0 rounded bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-900">
                    {t("employeeSchedule.changedBadge")}
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {colleagues.length > 0
                  ? t("employeeSchedule.withYou", {
                      names: colleagues.map((c) => c.full_name).join(", "),
                    })
                  : t("employeeSchedule.alone")}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

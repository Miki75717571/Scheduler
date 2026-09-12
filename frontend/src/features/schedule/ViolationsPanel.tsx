import { useTranslation } from "react-i18next";

import type { ScheduleViolation } from "../../api/types";
import { cn } from "../../lib/utils";
import { formatShortDate, translateViolation } from "./violationMessages";

export interface ViolationJumpTarget {
  date: string | null;
  userId: string | null;
}

interface ViolationsPanelProps {
  violations: ScheduleViolation[];
  nameById: Record<string, string>;
  dateBySlotId: Record<string, string>;
  onJump: (target: ViolationJumpTarget) => void;
}

// A violation names a slot, a date param (ONE_SHIFT_PER_DAY/MAX_CONSECUTIVE_DAYS),
// or neither (MIN/MAX_SHIFTS_PER_MONTH, MAX_WEEKEND_SHIFTS span the whole
// month) - "jump" degrades gracefully: to the day if one is derivable, to the
// employee filter otherwise.
function jumpTargetFor(v: ScheduleViolation, dateBySlotId: Record<string, string>): ViolationJumpTarget {
  const params = v.message_params;
  const date =
    (v.shift_slot_id && dateBySlotId[v.shift_slot_id]) ||
    (typeof params.date === "string" ? params.date : null) ||
    (typeof params.start === "string" ? params.start : null) ||
    null;
  return { date, userId: v.user_id };
}

export function ViolationsPanel({ violations, nameById, dateBySlotId, onJump }: ViolationsPanelProps) {
  const { t, i18n } = useTranslation();
  const errors = violations.filter((v) => v.severity === "ERROR");
  const warnings = violations.filter((v) => v.severity === "WARNING");

  if (violations.length === 0) {
    return (
      <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
        {t("schedule.violationsNone")}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold">{t("schedule.violationsTitle")}</h2>
      {errors.length > 0 && (
        <ViolationGroup
          heading={t("schedule.violationsErrors", { count: errors.length })}
          items={errors}
          nameById={nameById}
          dateBySlotId={dateBySlotId}
          onJump={onJump}
          severity="ERROR"
          language={i18n.language}
        />
      )}
      {warnings.length > 0 && (
        <ViolationGroup
          heading={t("schedule.violationsWarnings", { count: warnings.length })}
          items={warnings}
          nameById={nameById}
          dateBySlotId={dateBySlotId}
          onJump={onJump}
          severity="WARNING"
          language={i18n.language}
        />
      )}
    </div>
  );
}

function ViolationGroup({
  heading,
  items,
  nameById,
  dateBySlotId,
  onJump,
  severity,
  language,
}: {
  heading: string;
  items: ScheduleViolation[];
  nameById: Record<string, string>;
  dateBySlotId: Record<string, string>;
  onJump: (target: ViolationJumpTarget) => void;
  severity: "ERROR" | "WARNING";
  language: string;
}) {
  const { t } = useTranslation();
  return (
    <div>
      <h3
        className={cn(
          "text-xs font-semibold uppercase tracking-wide",
          severity === "ERROR" ? "text-red-700" : "text-amber-700",
        )}
      >
        {heading}
      </h3>
      <ul className="mt-1 space-y-1">
        {items.map((v, index) => (
          // Violations are recomputed wholesale on every change (no stable id
          // from the API) - index-in-severity-group is stable enough for a
          // list that fully re-renders together each time.
          <li key={`${severity}-${index}`}>
            <button
              type="button"
              onClick={() => onJump(jumpTargetFor(v, dateBySlotId))}
              className={cn(
                "w-full rounded border px-2 py-1.5 text-left text-xs hover:bg-secondary",
                severity === "ERROR" ? "border-red-300 bg-red-50" : "border-amber-300 bg-amber-50",
              )}
            >
              {v.shift_slot_id && dateBySlotId[v.shift_slot_id] && (
                <span className="font-medium">
                  {formatShortDate(dateBySlotId[v.shift_slot_id], language)}:{" "}
                </span>
              )}
              {v.user_id && nameById[v.user_id] && (
                <span className="font-medium">{nameById[v.user_id]}: </span>
              )}
              {translateViolation(v, t, language)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

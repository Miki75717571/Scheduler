import { useTranslation } from "react-i18next";

import type { FeasibilitySummary } from "../../api/types";
import { cn } from "../../lib/utils";

interface FeasibilityPanelProps {
  summary: FeasibilitySummary;
}

interface CheckRowProps {
  ok: boolean | null;
  label: string;
}

function CheckRow({ ok, label }: CheckRowProps) {
  const { t } = useTranslation();
  const icon = ok === null ? "•" : ok ? "✓" : "✕";
  const style =
    ok === null
      ? "text-muted-foreground"
      : ok
        ? "text-emerald-700"
        : "text-destructive font-medium";
  return (
    <li className={cn("flex items-start gap-2 text-sm", style)}>
      <span aria-hidden className="shrink-0">
        {icon}
      </span>
      <span>
        {label}
        {ok === null && <span className="ml-1 text-xs">{t("feasibility.notYetKnown")}</span>}
      </span>
    </li>
  );
}

// The pre-generate reality check the task brief asked for: "with 7 people
// this system is fragile - I need to see that before I generate, not after."
// Every number here is derived, never guessed - see
// backend/app/services/period_service.py's `feasibility_summary`.
export function FeasibilityPanel({ summary }: FeasibilityPanelProps) {
  const { t } = useTranslation();

  return (
    <section className="space-y-2 rounded-lg border border-border p-3">
      <h2 className="text-sm font-semibold">{t("feasibility.title")}</h2>
      <p className="text-sm text-muted-foreground">
        {t("feasibility.overview", {
          totalSlots: summary.total_slots,
          employees: summary.active_employee_count,
          avg: summary.avg_shifts_per_employee.toFixed(1),
        })}
      </p>
      <ul className="space-y-1.5">
        <CheckRow
          ok={summary.min_shifts_feasible}
          label={
            summary.min_shifts_per_month === null
              ? t("feasibility.minShiftsNoRule")
              : t("feasibility.minShifts", {
                  employees: summary.active_employee_count,
                  min: summary.min_shifts_per_month,
                  totalSlots: summary.total_slots,
                })
          }
        />
        <CheckRow
          ok={summary.availability_feasible}
          label={t("feasibility.availability", {
            declared: summary.total_declared,
            totalSlots: summary.total_slots,
          })}
        />
        <CheckRow
          ok={summary.weekend_feasible}
          label={
            summary.max_weekend_shifts === null
              ? t("feasibility.weekendNoRule")
              : t("feasibility.weekend", {
                  weekendSlots: summary.weekend_slot_count,
                  employees: summary.active_employee_count,
                  max: summary.max_weekend_shifts,
                })
          }
        />
      </ul>

      {summary.not_submitted.length > 0 && (
        <div className="border-t border-border pt-2">
          <p className="text-xs font-semibold text-amber-700">
            {t("feasibility.notSubmittedTitle", { count: summary.not_submitted.length })}
          </p>
          <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            {summary.not_submitted.map((e) => (
              <li key={e.user_id}>
                {t("feasibility.notSubmittedEntry", {
                  name: e.full_name,
                  count: e.estimated_slots_uncovered,
                })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

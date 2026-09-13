import { useTranslation } from "react-i18next";

import type { ScheduleDiagnostics } from "../../../api/types";
import { formatShortDate } from "../violationMessages";
import { translateDiagnostic } from "./diagnosticsMessages";

interface RunDiagnosticsProps {
  diagnostics: ScheduleDiagnostics;
  nameById: Record<string, string>;
  shiftTypeNameByCode: Record<string, string>;
  onJumpToDate?: (date: string) => void;
}

// The "why" screen the whole generate flow exists to support (task brief:
// "that's the difference between a tool I trust and a black box") - every
// understaffed slot and every below-minimum employee, each with the reason a
// manager can actually act on rather than just a red count.
export function RunDiagnostics({
  diagnostics,
  nameById,
  shiftTypeNameByCode,
  onJumpToDate,
}: RunDiagnosticsProps) {
  const { t, i18n } = useTranslation();

  if (
    diagnostics.slots.length === 0 &&
    diagnostics.employees.length === 0 &&
    diagnostics.rest_conflicts.length === 0
  ) {
    return (
      <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
        {t("generate.diagnosticsNoIssues")}
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <h3 className="text-sm font-semibold">{t("generate.diagnosticsTitle")}</h3>

      {diagnostics.rest_conflicts.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-amber-700">
            {t("generate.diagnosticsRestConflictsTitle", {
              count: diagnostics.rest_conflicts.length,
            })}
          </h4>
          <ul className="space-y-1">
            {diagnostics.rest_conflicts.map((conflict) => (
              <li
                key={`${conflict.from_weekday}-${conflict.from_shift_type_code}-${conflict.to_weekday}-${conflict.to_shift_type_code}`}
                className="rounded border border-amber-300 bg-amber-50 p-2 text-xs"
              >
                {translateDiagnostic(
                  conflict.message_key,
                  conflict.message_params,
                  t,
                  i18n.language,
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {diagnostics.slots.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-red-700">
            {t("generate.diagnosticsSlotsTitle", { count: diagnostics.slots.length })}
          </h4>
          <ul className="space-y-2">
            {diagnostics.slots.map((slot) => (
              <li
                key={slot.slot_id}
                className="rounded border border-red-300 bg-red-50 p-2 text-xs"
              >
                <button
                  type="button"
                  onClick={() => onJumpToDate?.(slot.date)}
                  className="font-medium hover:underline"
                >
                  {formatShortDate(slot.date, i18n.language)} —{" "}
                  {shiftTypeNameByCode[slot.shift_type_code] ?? slot.shift_type_code}
                </button>
                <p>
                  {translateDiagnostic(slot.message_key, slot.message_params, t, i18n.language)}
                </p>
                {slot.unused_available.length > 0 && (
                  <div className="mt-1 border-t border-red-200 pt-1">
                    <p className="font-semibold text-red-800">
                      {t("generate.diagnosticsUnusedTitle")}
                    </p>
                    <ul className="space-y-0.5">
                      {slot.unused_available.map((u) => (
                        <li key={u.employee_id}>
                          <span className="font-medium">{u.full_name}</span>{" "}
                          <span className="text-[11px] uppercase text-muted-foreground">
                            (
                            {u.level === "PREFERRED"
                              ? t("schedule.pickerPreferred")
                              : t("schedule.pickerAvailable")}
                            )
                          </span>
                          {" — "}
                          {translateDiagnostic(u.message_key, u.message_params, t, i18n.language)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {diagnostics.employees.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-amber-700">
            {t("generate.diagnosticsEmployeesTitle", { count: diagnostics.employees.length })}
          </h4>
          <ul className="space-y-1">
            {diagnostics.employees.map((employee) => (
              <li
                key={employee.employee_id}
                className="rounded border border-amber-300 bg-amber-50 p-2 text-xs"
              >
                <span className="font-medium">
                  {nameById[employee.employee_id] ?? employee.employee_id}
                </span>
                {": "}
                {translateDiagnostic(
                  employee.message_key,
                  employee.message_params,
                  t,
                  i18n.language,
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

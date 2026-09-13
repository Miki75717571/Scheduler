import type { TFunction } from "i18next";

import { formatShortDate } from "../violationMessages";

// Solver diagnostics (backend/app/scheduling/explain.py) carry message keys
// that are already fully qualified ("solver.slot_understaffed",
// "solver.unused_rest_rule", ...) - unlike schedule_validator.py's
// violations, there's no extra namespace prefix to add before calling `t`.
export function translateDiagnostic(
  messageKey: string,
  params: Record<string, unknown>,
  t: TFunction,
  language: string,
): string {
  const formatted: Record<string, unknown> = { ...params };
  if (typeof formatted.date === "string") {
    formatted.date = formatShortDate(formatted.date, language);
  }
  return t(messageKey, { ...formatted, defaultValue: messageKey });
}

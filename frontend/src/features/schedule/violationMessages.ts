import type { TFunction } from "i18next";

import type { ScheduleViolation } from "../../api/types";
import { parseIsoDate } from "../../lib/weekdays";

const DATE_PARAM_KEYS = ["date", "start", "end"];

export function formatShortDate(isoDate: string, language: string): string {
  return new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    day: "numeric",
    month: "short",
  }).format(parseIsoDate(isoDate));
}

function formatDate(value: unknown, language: string): unknown {
  if (typeof value !== "string") return value;
  try {
    return formatShortDate(value, language);
  } catch {
    return value;
  }
}

// Schedule-phase violations (backend/app/rules/schedule_validator.py) reuse
// plain ISO date strings and raw shift-slot ids in message_params - the
// frontend only formats/translates, never reimplements the rule logic
// (CLAUDE.md), mirroring lib/ruleMessages.ts's approach for the
// availability-phase equivalents.
export function translateViolation(
  v: ScheduleViolation,
  t: TFunction,
  language: string,
): string {
  const params: Record<string, unknown> = { ...v.message_params };
  for (const key of DATE_PARAM_KEYS) {
    if (key in params) params[key] = formatDate(params[key], language);
  }
  return t(`violations.${v.message_key}`, { ...params, defaultValue: v.message_key });
}

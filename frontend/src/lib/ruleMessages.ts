import type { TFunction } from "i18next";

import type { RuleCheckResult, ShiftType } from "../api/types";

// Rule params come back as raw codes ("FRI", "EVENING") from the backend -
// the frontend only translates, never reimplements the rule logic (CLAUDE.md).
// weekday codes go through the weekdaysFull.* keys; shift codes are resolved
// against the real ShiftType rows so a renamed/added shift type never
// requires a frontend change.
export function translateRuleParams(
  result: RuleCheckResult,
  shiftTypesByCode: Record<string, ShiftType>,
  t: TFunction,
  language: string,
): Record<string, unknown> {
  const params: Record<string, unknown> = { ...result.message_params };
  if (typeof params.weekday === "string") {
    params.weekday = t(`weekdaysFull.${params.weekday}`, { defaultValue: params.weekday });
  }
  if (typeof params.shift === "string") {
    const shiftType = shiftTypesByCode[params.shift];
    params.shift = shiftType
      ? language === "pl"
        ? shiftType.name_pl
        : shiftType.name_en
      : params.shift;
  }
  return params;
}

export function shiftTypesByCode(shiftTypes: ShiftType[]): Record<string, ShiftType> {
  return Object.fromEntries(shiftTypes.map((st) => [st.code, st]));
}

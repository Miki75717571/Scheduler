// Mirrors backend/app/rules/weekdays.py's bit layout (Mon=1<<0 ... Sun=1<<6)
// so `active_weekdays` bitmasks from ShiftType decode identically on both
// sides. JS's Date.getDay() is Sun=0..Sat=6, hence the (day + 6) % 7 shift
// to land on the same Mon=0..Sun=6 ordering the backend uses.

export const WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;
export type WeekdayCode = (typeof WEEKDAY_CODES)[number];

// Parses "YYYY-MM-DD" via its numeric parts (not `new Date(isoString)`,
// which parses as UTC and can land on the wrong local day) - same
// never-a-UTC-timestamp discipline CLAUDE.md requires for shift dates.
export function parseIsoDate(isoDate: string): Date {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function weekdayCodeOf(isoDate: string): WeekdayCode {
  const jsDay = parseIsoDate(isoDate).getDay();
  return WEEKDAY_CODES[(jsDay + 6) % 7];
}

export function weekdayBit(code: WeekdayCode): number {
  return 1 << WEEKDAY_CODES.indexOf(code);
}

export function isActiveOnWeekday(activeWeekdaysMask: number, code: WeekdayCode): boolean {
  return (activeWeekdaysMask & weekdayBit(code)) !== 0;
}

export function isWeekend(code: WeekdayCode): boolean {
  return code === "SAT" || code === "SUN";
}

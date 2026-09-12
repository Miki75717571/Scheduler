export type Countdown =
  | { kind: "none" }
  | { kind: "passed" }
  | { kind: "days"; count: number }
  | { kind: "hours"; count: number };

export function countdownTo(deadlineIso: string | null, now: Date = new Date()): Countdown {
  if (!deadlineIso) return { kind: "none" };
  const diffMs = new Date(deadlineIso).getTime() - now.getTime();
  if (diffMs <= 0) return { kind: "passed" };
  const hours = diffMs / (1000 * 60 * 60);
  if (hours >= 24) return { kind: "days", count: Math.ceil(hours / 24) };
  return { kind: "hours", count: Math.ceil(hours) };
}

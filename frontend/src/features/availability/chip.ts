import type { AvailabilityStatus } from "../../api/types";

// unavailable -> available -> preferred -> unavailable
export const NEXT_STATUS: Record<AvailabilityStatus, AvailabilityStatus> = {
  UNAVAILABLE: "AVAILABLE",
  AVAILABLE: "PREFERRED",
  PREFERRED: "UNAVAILABLE",
};

// Distinguishable without relying on colour alone: each state also gets its
// own icon glyph and border weight/style, for colour-blind staff reading
// this off a phone in bright kitchen light.
export const STATUS_ICON: Record<AvailabilityStatus, string> = {
  UNAVAILABLE: "–", // –
  AVAILABLE: "✓", // ✓
  PREFERRED: "★", // ★
};

export const STATUS_STYLE: Record<AvailabilityStatus, string> = {
  UNAVAILABLE: "border border-slate-300 bg-slate-100 text-slate-500",
  AVAILABLE: "border-2 border-emerald-500 bg-emerald-100 text-emerald-800",
  PREFERRED: "border-2 border-amber-500 bg-amber-100 text-amber-900 ring-2 ring-amber-300",
};

export const CLOSED_STYLE = "border border-dashed border-slate-300 bg-slate-50 text-slate-400";
export const CLOSED_ICON = "⛔"; // ⛔

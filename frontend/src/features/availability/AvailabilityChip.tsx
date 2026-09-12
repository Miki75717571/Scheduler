import { useTranslation } from "react-i18next";

import type { AvailabilityStatus } from "../../api/types";
import { cn } from "../../lib/utils";
import { CLOSED_ICON, CLOSED_STYLE, STATUS_ICON, STATUS_STYLE } from "./chip";

interface AvailabilityChipProps {
  status: AvailabilityStatus;
  label: string;
  sublabel?: string;
  closed?: boolean;
  disabled?: boolean;
  onCycle: () => void;
}

export function AvailabilityChip({
  status,
  label,
  sublabel,
  closed,
  disabled,
  onCycle,
}: AvailabilityChipProps) {
  const { t } = useTranslation();

  if (closed) {
    return (
      <div
        className={cn(
          "flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-2 py-1.5 text-xs font-medium",
          CLOSED_STYLE,
        )}
      >
        <span aria-hidden className="text-base leading-none">
          {CLOSED_ICON}
        </span>
        <span className="leading-tight">{t("availability.closedDay")}</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onCycle}
      aria-pressed={status !== "UNAVAILABLE"}
      aria-label={`${label} — ${t(`availability.chipState.${status}`)}`}
      className={cn(
        "flex min-h-[44px] min-w-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        STATUS_STYLE[status],
      )}
    >
      <span aria-hidden className="text-base leading-none">
        {STATUS_ICON[status]}
      </span>
      <span className="leading-tight">{label}</span>
      {sublabel && <span className="text-[10px] leading-tight opacity-80">{sublabel}</span>}
    </button>
  );
}

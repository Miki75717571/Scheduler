import { useTranslation } from "react-i18next";

import type { AvailabilityStatus, ShiftSlot, ShiftType } from "../../api/types";
import { cn } from "../../lib/utils";
import { isWeekend, parseIsoDate, weekdayCodeOf } from "../../lib/weekdays";
import { AvailabilityChip } from "./AvailabilityChip";

interface DayTileProps {
  dateIso: string;
  slots: ShiftSlot[];
  shiftTypesById: Record<string, ShiftType>;
  statusBySlotId: Record<string, AvailabilityStatus>;
  editable: boolean;
  onCycle: (slotId: string) => void;
}

export function DayTile({
  dateIso,
  slots,
  shiftTypesById,
  statusBySlotId,
  editable,
  onCycle,
}: DayTileProps) {
  const { t, i18n } = useTranslation();
  const weekday = weekdayCodeOf(dateIso);
  const weekend = isWeekend(weekday);
  const dayNumber = parseIsoDate(dateIso).getDate();
  const orderedSlots = [...slots].sort(
    (a, b) =>
      shiftTypesById[a.shift_type_id].sort_order - shiftTypesById[b.shift_type_id].sort_order,
  );

  return (
    <div
      className={cn(
        "flex items-stretch gap-2 rounded-lg border border-border p-2",
        weekend ? "bg-slate-50" : "bg-background",
      )}
    >
      <div className="flex w-12 shrink-0 flex-col items-center justify-center text-center">
        <span className="text-[11px] font-medium uppercase text-muted-foreground">
          {t(`weekdaysShort.${weekday}`)}
        </span>
        <span className="text-lg font-semibold leading-tight">{dayNumber}</span>
      </div>
      <div className="flex flex-1 gap-2">
        {orderedSlots.map((slot) => {
          const shiftType = shiftTypesById[slot.shift_type_id];
          const name = i18n.language === "pl" ? shiftType.name_pl : shiftType.name_en;
          return (
            <AvailabilityChip
              key={slot.id}
              status={statusBySlotId[slot.id] ?? "UNAVAILABLE"}
              label={name}
              sublabel={slot.start_time.slice(0, 5)}
              closed={slot.is_closed}
              disabled={!editable}
              onCycle={() => onCycle(slot.id)}
            />
          );
        })}
      </div>
    </div>
  );
}

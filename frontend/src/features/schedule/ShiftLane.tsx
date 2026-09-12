import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Assignment, ScheduleViolation, ShiftSlot, ShiftType } from "../../api/types";
import { cn } from "../../lib/utils";
import { AssignmentChip } from "./AssignmentChip";
import { SLOT_STATUS_ICON, SLOT_STATUS_STYLE, computeSlotStatus } from "./colorLogic";

interface DragPayload {
  assignmentId: string;
  sourceSlotId: string;
}

interface ShiftLaneProps {
  slot: ShiftSlot;
  shiftType: ShiftType;
  assignments: Assignment[];
  slotViolations: ScheduleViolation[];
  selectedEmployeeId: string | null;
  language: string;
  onAdd: () => void;
  onToggleLock: (assignment: Assignment) => void;
  onRemove: (assignment: Assignment) => void;
  onDropAssignment: (payload: DragPayload) => void;
}

export function ShiftLane({
  slot,
  shiftType,
  assignments,
  slotViolations,
  selectedEmployeeId,
  language,
  onAdd,
  onToggleLock,
  onRemove,
  onDropAssignment,
}: ShiftLaneProps) {
  const { t } = useTranslation();
  const [dragOver, setDragOver] = useState(false);
  const status = computeSlotStatus(slot, assignments.length, slotViolations);
  const name = language === "pl" ? shiftType.name_pl : shiftType.name_en;

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragOver(false);
    const raw = event.dataTransfer.getData("text/plain");
    if (!raw) return;
    try {
      const payload = JSON.parse(raw) as DragPayload;
      if (payload.sourceSlotId !== slot.id) onDropAssignment(payload);
    } catch {
      // Not one of our drag payloads - ignore.
    }
  }

  return (
    <div
      onDragOver={(event) => {
        if (!slot.is_closed) {
          event.preventDefault();
          setDragOver(true);
        }
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      role="group"
      aria-label={`${name} — ${t(`schedule.staffCount`, { assigned: assignments.length, required: slot.required_staff })}`}
      className={cn(
        "rounded border px-1 py-1 text-xs",
        SLOT_STATUS_STYLE[status],
        dragOver && "outline outline-2 outline-offset-1 outline-sky-500",
      )}
    >
      <div className="mb-0.5 flex items-center justify-between gap-1">
        <span className="truncate font-medium" title={name}>
          {shiftType.code.slice(0, 3)}
        </span>
        <span
          className="shrink-0"
          aria-label={status}
          title={t(`schedule.staffCount`, { assigned: assignments.length, required: slot.required_staff })}
        >
          {SLOT_STATUS_ICON[status]} {assignments.length}/{slot.required_staff}
        </span>
      </div>

      {slot.is_closed ? (
        <p className="text-[11px] text-slate-400 print:text-black">{t("schedule.closedDay")}</p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {assignments.map((assignment) => (
            <AssignmentChip
              key={assignment.id}
              assignment={assignment}
              dimmed={selectedEmployeeId !== null && assignment.user_id !== selectedEmployeeId}
              onToggleLock={() => onToggleLock(assignment)}
              onRemove={() => onRemove(assignment)}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData(
                  "text/plain",
                  JSON.stringify({ assignmentId: assignment.id, sourceSlotId: slot.id }),
                );
              }}
              onDragEnd={() => setDragOver(false)}
            />
          ))}
          <button
            type="button"
            onClick={onAdd}
            className="rounded border border-dashed border-slate-400 px-1.5 py-0.5 text-slate-600 hover:bg-white print:hidden"
          >
            {t("schedule.emptySlotAdd")}
          </button>
        </div>
      )}
    </div>
  );
}

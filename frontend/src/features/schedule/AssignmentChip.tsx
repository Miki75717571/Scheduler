import { useTranslation } from "react-i18next";

import type { Assignment } from "../../api/types";
import { cn } from "../../lib/utils";

interface AssignmentChipProps {
  assignment: Assignment;
  dimmed: boolean;
  onToggleLock: () => void;
  onRemove: () => void;
  onDragStart: (event: React.DragEvent) => void;
  onDragEnd: () => void;
}

// A chip is draggable only while unlocked - locking is the explicit "don't
// move this" signal (ARCHITECTURE.md ss3.6's is_locked, extended here to
// manual drag as well as the future solver), so a locked chip must be
// unlocked first before it can be dragged or removed.
export function AssignmentChip({
  assignment,
  dimmed,
  onToggleLock,
  onRemove,
  onDragStart,
  onDragEnd,
}: AssignmentChipProps) {
  const { t } = useTranslation();

  return (
    <div
      draggable={!assignment.is_locked}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        "group flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs leading-tight print:border-black print:text-black",
        assignment.is_locked
          ? "border-2 border-slate-700 bg-slate-100 font-semibold"
          : "border-slate-300 bg-white",
        !assignment.is_locked && "cursor-grab active:cursor-grabbing",
        dimmed && "opacity-30",
        assignment.modified_after_publish && "ring-2 ring-sky-400",
      )}
      title={assignment.modified_after_publish ? t("schedule.publishedChangedWarning", { count: 1 }) : undefined}
    >
      <button
        type="button"
        onClick={onToggleLock}
        className="max-w-[8rem] truncate text-left"
        aria-label={
          assignment.is_locked
            ? `${assignment.full_name} — ${t("schedule.unlockChip")}`
            : `${assignment.full_name} — ${t("schedule.lockChip")}`
        }
        title={assignment.is_locked ? t("schedule.unlockChip") : t("schedule.lockChip")}
      >
        {assignment.is_locked && <span aria-hidden="true">🔒 </span>}
        {assignment.full_name}
      </button>
      <button
        type="button"
        onClick={onRemove}
        disabled={assignment.is_locked}
        aria-label={`${t("schedule.removeChip")} ${assignment.full_name}`}
        title={assignment.is_locked ? t("schedule.unlockChip") : t("schedule.removeChip")}
        className="text-slate-400 opacity-0 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-0 print:hidden"
      >
        ×
      </button>
    </div>
  );
}

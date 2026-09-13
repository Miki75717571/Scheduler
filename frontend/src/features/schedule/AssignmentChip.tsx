import { useTranslation } from "react-i18next";

import type { Assignment } from "../../api/types";
import { cn } from "../../lib/utils";

interface AssignmentChipProps {
  assignment: Assignment;
  dimmed: boolean;
  onToggleLock: () => void;
  onRemove: () => void;
  onOpenDetail: () => void;
  onDragStart: (event: React.DragEvent) => void;
  onDragEnd: () => void;
}

// A chip is draggable only while unlocked - locking is the explicit "don't
// move this" signal (ARCHITECTURE.md ss3.6's is_locked, extended here to
// manual drag as well as the solver), so a locked chip must be unlocked
// first before it can be dragged or removed. AUTO vs MANUAL gets its own
// badge (dashed border for AUTO) so a manager can tell at a glance which
// chips came from the solver without opening each one (task brief "AUTO and
// MANUAL assignments visually distinguishable").
export function AssignmentChip({
  assignment,
  dimmed,
  onToggleLock,
  onRemove,
  onOpenDetail,
  onDragStart,
  onDragEnd,
}: AssignmentChipProps) {
  const { t } = useTranslation();

  return (
    <div
      draggable={!assignment.is_locked}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onOpenDetail}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpenDetail();
        }
      }}
      className={cn(
        "group flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs leading-tight print:border-black print:text-black",
        assignment.is_locked
          ? "border-2 border-slate-700 bg-slate-100 font-semibold"
          : assignment.source === "AUTO"
            ? "border-dashed border-indigo-400 bg-indigo-50"
            : "border-slate-300 bg-white",
        !assignment.is_locked && "cursor-grab active:cursor-grabbing",
        dimmed && "opacity-30",
        assignment.modified_after_publish && "ring-2 ring-sky-400",
      )}
      title={
        assignment.modified_after_publish
          ? t("schedule.publishedChangedWarning", { count: 1 })
          : undefined
      }
    >
      <span
        aria-hidden="true"
        className="shrink-0 text-[10px] font-semibold text-muted-foreground"
        title={assignment.source === "AUTO" ? t("schedule.autoBadge") : t("schedule.manualBadge")}
      >
        {assignment.source === "AUTO" ? "A" : "M"}
      </span>
      <span className="max-w-[8rem] truncate text-left" aria-label={assignment.full_name}>
        {assignment.is_locked && <span aria-hidden="true">🔒 </span>}
        {assignment.full_name}
      </span>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onToggleLock();
        }}
        aria-label={
          assignment.is_locked
            ? `${assignment.full_name} — ${t("schedule.unlockChip")}`
            : `${assignment.full_name} — ${t("schedule.lockChip")}`
        }
        title={assignment.is_locked ? t("schedule.unlockChip") : t("schedule.lockChip")}
        className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 print:hidden"
      >
        {assignment.is_locked ? "🔓" : "🔒"}
      </button>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onRemove();
        }}
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

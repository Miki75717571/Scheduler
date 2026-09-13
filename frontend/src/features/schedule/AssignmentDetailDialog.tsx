import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import type { Assignment } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { fetchAvailableEmployees } from "./api";

interface AssignmentDetailDialogProps {
  assignment: Assignment;
  shiftTypeName: string;
  dateLabel: string;
  periodId: string;
  onClose: () => void;
}

// "Clicking any assignment explains it: was it AUTO or MANUAL, was this
// person AVAILABLE or PREFERRED for it, is it locked" - every fact here
// already exists somewhere (the assignment row, or the same
// available-employees lookup the assign picker already uses), this dialog
// just puts them in one place instead of making the manager go find them.
export function AssignmentDetailDialog({
  assignment,
  shiftTypeName,
  dateLabel,
  periodId,
  onClose,
}: AssignmentDetailDialogProps) {
  const { t } = useTranslation();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const candidatesQuery = useQuery({
    queryKey: ["available-employees", periodId, assignment.shift_slot_id],
    queryFn: () => fetchAvailableEmployees(periodId, assignment.shift_slot_id),
  });

  const candidate = candidatesQuery.data?.find((c) => c.user_id === assignment.user_id);

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4 print:hidden"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="assignment-detail-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-sm space-y-3 rounded-lg bg-background p-4 shadow-xl"
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="assignment-detail-title" className="text-sm font-semibold">
            {t("schedule.detailTitle", {
              name: assignment.full_name,
              shift: shiftTypeName,
              date: dateLabel,
            })}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("schedule.pickerClose")}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>

        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">{t("schedule.detailSource")}</dt>
            <dd>
              {assignment.source === "AUTO"
                ? t("schedule.detailSourceAuto")
                : t("schedule.detailSourceManual")}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">{t("schedule.detailAvailability")}</dt>
            <dd>
              {candidatesQuery.isLoading && t("common.loading")}
              {candidatesQuery.error !== null && <ApiErrorText error={candidatesQuery.error} />}
              {!candidatesQuery.isLoading && candidatesQuery.error === null && (
                <>
                  {candidate?.status === "PREFERRED" && t("schedule.detailAvailabilityPreferred")}
                  {candidate?.status === "AVAILABLE" && t("schedule.detailAvailabilityAvailable")}
                  {!candidate && t("schedule.detailAvailabilityUnknown")}
                </>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">{t("schedule.lockedBadge")}</dt>
            <dd>
              {assignment.is_locked ? t("schedule.detailLocked") : t("schedule.detailUnlocked")}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

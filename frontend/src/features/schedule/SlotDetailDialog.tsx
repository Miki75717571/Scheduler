import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import type { SlotDiagnostic } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { translateDiagnostic } from "./generate/diagnosticsMessages";
import { fetchAvailableEmployees } from "./api";

interface SlotDetailDialogProps {
  slotId: string;
  shiftTypeName: string;
  dateLabel: string;
  periodId: string;
  diagnostic: SlotDiagnostic | null;
  onClose: () => void;
}

// "Clicking an empty or understaffed slot explains it: how many people were
// available, and why the ones who were available weren't used" - when the
// latest solver run already diagnosed this exact slot, use its reasons
// (already_assigned_same_day / contract_max_reached / rest_rule / ...);
// otherwise fall back to the plain available-employees list the assign
// picker already uses, with a note that a run is needed for the full reason.
export function SlotDetailDialog({
  slotId,
  shiftTypeName,
  dateLabel,
  periodId,
  diagnostic,
  onClose,
}: SlotDetailDialogProps) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const candidatesQuery = useQuery({
    queryKey: ["available-employees", periodId, slotId],
    queryFn: () => fetchAvailableEmployees(periodId, slotId),
    enabled: diagnostic === null,
  });

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4 print:hidden"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="slot-detail-title"
        onClick={(event) => event.stopPropagation()}
        className="max-h-[80vh] w-full max-w-sm space-y-3 overflow-y-auto rounded-lg bg-background p-4 shadow-xl"
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="slot-detail-title" className="text-sm font-semibold">
            {t("schedule.slotDetailTitle", { shift: shiftTypeName, date: dateLabel })}
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

        {diagnostic ? (
          <div className="space-y-2 text-sm">
            <p>
              {translateDiagnostic(
                diagnostic.message_key,
                diagnostic.message_params,
                t,
                i18n.language,
              )}
            </p>
            {diagnostic.unused_available.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-muted-foreground">
                  {t("schedule.slotDetailUnusedTitle")}
                </p>
                <ul className="mt-1 space-y-1 text-xs">
                  {diagnostic.unused_available.map((u) => (
                    <li key={u.employee_id} className="rounded border border-border px-2 py-1">
                      <span className="font-medium">{u.full_name}</span>{" "}
                      <span className="text-[11px] uppercase text-muted-foreground">
                        (
                        {u.level === "PREFERRED"
                          ? t("schedule.pickerPreferred")
                          : t("schedule.pickerAvailable")}
                        )
                      </span>
                      {" — "}
                      {translateDiagnostic(u.message_key, u.message_params, t, i18n.language)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                {t("schedule.slotDetailAvailableCount", { count: 0 })}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2 text-sm">
            {candidatesQuery.isLoading && <p>{t("common.loading")}</p>}
            {candidatesQuery.error !== null && candidatesQuery.error !== undefined && (
              <ApiErrorText error={candidatesQuery.error} />
            )}
            {candidatesQuery.data && (
              <>
                <p>
                  {t("schedule.slotDetailAvailableCount", { count: candidatesQuery.data.length })}
                </p>
                <ul className="space-y-1 text-xs">
                  {candidatesQuery.data.map((c) => (
                    <li key={c.user_id}>
                      {c.full_name}{" "}
                      <span className="text-[11px] uppercase text-muted-foreground">
                        (
                        {c.status === "PREFERRED"
                          ? t("schedule.pickerPreferred")
                          : t("schedule.pickerAvailable")}
                        )
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-muted-foreground">{t("schedule.slotDetailNoRunYet")}</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

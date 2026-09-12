import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  AvailabilityEntry,
  AvailabilityStatus,
  RuleCheckResult,
  ShiftSlot,
  ShiftType,
  SubmissionStatus,
} from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { Button } from "../../components/ui/button";
import { useAutosave } from "../../hooks/useAutosave";
import { shiftTypesByCode } from "../../lib/ruleMessages";
import { submitAvailability, writeAvailability } from "./api";
import { BulkActionsBar } from "./BulkActionsBar";
import {
  allMorningsPatch,
  allWeekdayEveningsPatch,
  allWeekendsPatch,
  clearAllPatch,
  copyFromLastMonthPatch,
} from "./bulkActions";
import { NEXT_STATUS } from "./chip";
import { DayTile } from "./DayTile";
import { RequirementsBar } from "./RequirementsBar";
import { SaveStatusIndicator } from "./SaveStatusIndicator";

function groupByDate(slots: ShiftSlot[]): [string, ShiftSlot[]][] {
  const byDate: Record<string, ShiftSlot[]> = {};
  for (const slot of slots) {
    (byDate[slot.date] ??= []).push(slot);
  }
  return Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b));
}

function toStatusMap(
  slots: ShiftSlot[],
  entries: AvailabilityEntry[],
): Record<string, AvailabilityStatus> {
  const map: Record<string, AvailabilityStatus> = {};
  for (const slot of slots) map[slot.id] = "UNAVAILABLE";
  for (const entry of entries) map[entry.shift_slot_id] = entry.status;
  return map;
}

interface AvailabilityCalendarProps {
  periodId: string;
  userId: string;
  editable: boolean;
  readOnlyMessageKey: string | null;
  reopenedNotice: boolean;
  slots: ShiftSlot[];
  shiftTypes: ShiftType[];
  initialEntries: AvailabilityEntry[];
  initialValidation: RuleCheckResult[];
  initialSubmissionStatus: SubmissionStatus;
  previousSlots: ShiftSlot[] | null;
  previousStatusBySlotId: Record<string, AvailabilityStatus> | null;
}

export function AvailabilityCalendar({
  periodId,
  userId,
  editable,
  readOnlyMessageKey,
  reopenedNotice,
  slots,
  shiftTypes,
  initialEntries,
  initialValidation,
  initialSubmissionStatus,
  previousSlots,
  previousStatusBySlotId,
}: AvailabilityCalendarProps) {
  const { t } = useTranslation();

  const shiftTypesById = useMemo(
    () => Object.fromEntries(shiftTypes.map((st) => [st.id, st])),
    [shiftTypes],
  );
  const byCode = useMemo(() => shiftTypesByCode(shiftTypes), [shiftTypes]);

  const [statusBySlotId, setStatusBySlotId] = useState(() => toStatusMap(slots, initialEntries));
  const [dirty, setDirty] = useState(false);
  const [validation, setValidation] = useState(initialValidation);
  const [submissionStatus, setSubmissionStatus] = useState(initialSubmissionStatus);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const [justSubmitted, setJustSubmitted] = useState(false);

  const save = async (nextStatus: Record<string, AvailabilityStatus>) => {
    const entries = Object.entries(nextStatus).map(([shift_slot_id, status]) => ({
      shift_slot_id,
      status,
    }));
    const detail = await writeAvailability(periodId, userId, entries);
    setValidation(detail.validation);
    setSubmissionStatus(detail.submission.status);
    setDirty(false);
  };

  const { status: saveStatus, retry } = useAutosave(statusBySlotId, save, 800);

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  function applyPatch(patch: Record<string, AvailabilityStatus>) {
    setStatusBySlotId((prev) => ({ ...prev, ...patch }));
    setDirty(true);
    setJustSubmitted(false);
  }

  function handleCycle(slotId: string) {
    setStatusBySlotId((prev) => ({
      ...prev,
      [slotId]: NEXT_STATUS[prev[slotId] ?? "UNAVAILABLE"],
    }));
    setDirty(true);
    setJustSubmitted(false);
  }

  const hasHardFailure = validation.some((r) => r.severity === "HARD" && !r.passed);
  const submitDisabled = !editable || hasHardFailure || submitting || saveStatus === "saving";

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const detail = await submitAvailability(periodId, userId);
      setValidation(detail.validation);
      setSubmissionStatus(detail.submission.status);
      setJustSubmitted(true);
    } catch (error) {
      setSubmitError(error);
    } finally {
      setSubmitting(false);
    }
  }

  const canCopyLastMonth = Boolean(
    previousSlots && previousStatusBySlotId && previousSlots.length > 0,
  );

  return (
    <div className="space-y-4 pb-28">
      {!editable && readOnlyMessageKey && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {t(readOnlyMessageKey)}
        </div>
      )}
      {editable && reopenedNotice && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {t("availability.reopenedNotice")}
        </div>
      )}

      <RequirementsBar validation={validation} shiftTypesByCode={byCode} />

      {editable && (
        <BulkActionsBar
          onAllMornings={() => applyPatch(allMorningsPatch(slots, shiftTypesById))}
          onAllWeekdayEvenings={() => applyPatch(allWeekdayEveningsPatch(slots, shiftTypesById))}
          onAllWeekends={() => applyPatch(allWeekendsPatch(slots))}
          onClearAll={() => applyPatch(clearAllPatch(slots))}
          onCopyLastMonth={
            canCopyLastMonth
              ? () =>
                  applyPatch(
                    copyFromLastMonthPatch(slots, previousSlots ?? [], previousStatusBySlotId ?? {}),
                  )
              : undefined
          }
        />
      )}

      <div className="space-y-2">
        {groupByDate(slots).map(([date, daySlots]) => (
          <DayTile
            key={date}
            dateIso={date}
            slots={daySlots}
            shiftTypesById={shiftTypesById}
            statusBySlotId={statusBySlotId}
            editable={editable}
            onCycle={handleCycle}
          />
        ))}
      </div>

      {editable && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 px-4 py-3 backdrop-blur">
          <div className="mx-auto max-w-2xl">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {t(`availability.submissionStatus.${submissionStatus}`)}
              </span>
              <SaveStatusIndicator status={saveStatus} onRetry={retry} />
            </div>
            <Button
              type="button"
              className="mt-2 w-full"
              disabled={submitDisabled}
              onClick={() => void handleSubmit()}
            >
              {submitting ? t("common.loading") : t("availability.submitButton")}
            </Button>
            {submitDisabled && !submitting && hasHardFailure && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("availability.submitDisabledHint")}
              </p>
            )}
            {justSubmitted && (
              <p className="mt-1 text-xs text-emerald-700">{t("availability.submitSuccess")}</p>
            )}
            {submitError !== null && <ApiErrorText error={submitError} className="mt-1 text-xs text-destructive" />}
          </div>
        </div>
      )}
    </div>
  );
}

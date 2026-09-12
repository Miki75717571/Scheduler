import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import type { PeriodState } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { fetchShiftTypes } from "../features/availability/api";
import {
  fetchPeriod,
  fetchSlots,
  fetchTracker,
  reopenAvailability,
  revokeReopenAvailability,
  updatePeriodState,
  updateSlot,
} from "../features/manager/api";
import { PeriodStateControls } from "../features/manager/PeriodStateControls";
import { SlotOverridesTable } from "../features/manager/SlotOverridesTable";
import { SubmissionTracker } from "../features/manager/SubmissionTracker";
import { countdownTo } from "../lib/countdown";

function monthLabel(year: number, month: number, language: string): string {
  return new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
}

export function ManagerPeriodDetailPage() {
  const { periodId } = useParams<{ periodId: string }>();
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [pendingReopenUserId, setPendingReopenUserId] = useState<string | null>(null);
  const [reopenError, setReopenError] = useState<unknown>(null);

  const periodQuery = useQuery({
    queryKey: ["period", periodId],
    queryFn: () => fetchPeriod(periodId as string),
    enabled: Boolean(periodId),
  });
  const trackerQuery = useQuery({
    queryKey: ["tracker", periodId],
    queryFn: () => fetchTracker(periodId as string),
    enabled: Boolean(periodId),
  });
  const slotsQuery = useQuery({
    queryKey: ["period-slots", periodId],
    queryFn: () => fetchSlots(periodId as string),
    enabled: Boolean(periodId),
  });
  const shiftTypesQuery = useQuery({ queryKey: ["shift-types"], queryFn: fetchShiftTypes });

  if (!periodId) return null;

  async function handleTransition(target: PeriodState) {
    // Errors propagate to PeriodStateControls, which shows them inline next
    // to the confirm button - no need to duplicate that here.
    await updatePeriodState(periodId as string, target);
    await queryClient.invalidateQueries({ queryKey: ["period", periodId] });
    await queryClient.invalidateQueries({ queryKey: ["tracker", periodId] });
    await queryClient.invalidateQueries({ queryKey: ["periods"] });
  }

  async function handleReopen(userId: string) {
    setPendingReopenUserId(userId);
    setReopenError(null);
    try {
      await reopenAvailability(periodId as string, userId);
      await queryClient.invalidateQueries({ queryKey: ["tracker", periodId] });
    } catch (error) {
      setReopenError(error);
    } finally {
      setPendingReopenUserId(null);
    }
  }

  async function handleRevokeReopen(userId: string) {
    setPendingReopenUserId(userId);
    setReopenError(null);
    try {
      await revokeReopenAvailability(periodId as string, userId);
      await queryClient.invalidateQueries({ queryKey: ["tracker", periodId] });
    } catch (error) {
      setReopenError(error);
    } finally {
      setPendingReopenUserId(null);
    }
  }

  async function handleSlotSave(
    slotId: string,
    payload: Parameters<typeof updateSlot>[2],
  ) {
    await updateSlot(periodId as string, slotId, payload);
    await queryClient.invalidateQueries({ queryKey: ["period-slots", periodId] });
  }

  if (periodQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (periodQuery.isError || !periodQuery.data) {
    return <ApiErrorText error={periodQuery.error} />;
  }

  const period = periodQuery.data;
  const countdown = countdownTo(period.availability_deadline);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{monthLabel(period.year, period.month, i18n.language)}</h1>
        <p className="text-sm text-muted-foreground">
          {t(`manager.stateLabel.${period.state}`)}
          {period.availability_deadline && (
            <>
              {" · "}
              {t("availability.deadline", {
                date: new Date(period.availability_deadline).toLocaleString(
                  i18n.language === "pl" ? "pl-PL" : "en-US",
                  { dateStyle: "medium", timeStyle: "short" },
                ),
              })}
            </>
          )}
          {countdown.kind === "days" && ` · ${t("manager.daysRemaining", { count: countdown.count })}`}
          {countdown.kind === "hours" && ` · ${t("availability.countdownHours", { count: countdown.count })}`}
          {countdown.kind === "passed" && ` · ${t("availability.countdownPassed")}`}
        </p>
      </div>

      <section className="space-y-2">
        <PeriodStateControls state={period.state} onTransition={handleTransition} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">{t("manager.trackerTitle")}</h2>
        {trackerQuery.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
        {trackerQuery.isError && <ApiErrorText error={trackerQuery.error} />}
        {reopenError !== null && <ApiErrorText error={reopenError} />}
        {trackerQuery.data && (
          <SubmissionTracker
            entries={trackerQuery.data}
            periodLocked={period.state === "LOCKED"}
            onReopen={handleReopen}
            onRevokeReopen={handleRevokeReopen}
            pendingUserId={pendingReopenUserId}
          />
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">{t("manager.slotsTitle")}</h2>
        {(slotsQuery.isLoading || shiftTypesQuery.isLoading) && (
          <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
        {(slotsQuery.isError || shiftTypesQuery.isError) && (
          <ApiErrorText error={slotsQuery.error ?? shiftTypesQuery.error} />
        )}
        {slotsQuery.data && shiftTypesQuery.data && (
          <SlotOverridesTable
            key={periodId}
            slots={slotsQuery.data}
            shiftTypesById={Object.fromEntries(shiftTypesQuery.data.map((st) => [st.id, st]))}
            onSave={handleSlotSave}
          />
        )}
      </section>
    </div>
  );
}

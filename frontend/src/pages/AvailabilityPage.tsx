import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { AvailabilityStatus, PeriodState, SchedulePeriod } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { AvailabilityCalendar } from "../features/availability/AvailabilityCalendar";
import { fetchAvailability, fetchPeriods, fetchShiftTypes, fetchSlots } from "../features/availability/api";
import { PeriodSelector } from "../features/availability/PeriodSelector";
import { useAuth } from "../lib/auth-context";

const READ_ONLY_KEY_BY_STATE: Record<PeriodState, string> = {
  DRAFT: "availability.readOnlyDraft",
  COLLECTING: "", // editable, never used
  LOCKED: "availability.readOnlyLocked",
  GENERATED: "availability.readOnlyGenerated",
  PUBLISHED: "availability.readOnlyPublished",
};

function pickDefaultPeriod(periods: SchedulePeriod[]): SchedulePeriod | null {
  if (periods.length === 0) return null;
  return (
    periods.find((p) => p.state === "COLLECTING") ??
    periods.find((p) => p.state === "LOCKED") ??
    periods[0]
  );
}

function previousPeriodOf(periods: SchedulePeriod[], period: SchedulePeriod): SchedulePeriod | null {
  const prevYear = period.month === 1 ? period.year - 1 : period.year;
  const prevMonth = period.month === 1 ? 12 : period.month - 1;
  return periods.find((p) => p.year === prevYear && p.month === prevMonth) ?? null;
}

export function AvailabilityPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null);

  const periodsQuery = useQuery({ queryKey: ["periods"], queryFn: fetchPeriods });
  const shiftTypesQuery = useQuery({ queryKey: ["shift-types"], queryFn: fetchShiftTypes });

  useEffect(() => {
    if (selectedPeriodId || !periodsQuery.data) return;
    const defaultPeriod = pickDefaultPeriod(periodsQuery.data);
    if (defaultPeriod) setSelectedPeriodId(defaultPeriod.id);
  }, [periodsQuery.data, selectedPeriodId]);

  const selectedPeriod = periodsQuery.data?.find((p) => p.id === selectedPeriodId) ?? null;
  const previousPeriod = useMemo(
    () => (periodsQuery.data && selectedPeriod ? previousPeriodOf(periodsQuery.data, selectedPeriod) : null),
    [periodsQuery.data, selectedPeriod],
  );

  const slotsQuery = useQuery({
    queryKey: ["period-slots", selectedPeriodId],
    queryFn: () => fetchSlots(selectedPeriodId as string),
    enabled: Boolean(selectedPeriodId),
  });

  const detailQuery = useQuery({
    queryKey: ["availability-detail", selectedPeriodId, user?.id],
    queryFn: () => fetchAvailability(selectedPeriodId as string, user!.id),
    enabled: Boolean(selectedPeriodId && user),
  });

  const previousSlotsQuery = useQuery({
    queryKey: ["period-slots", previousPeriod?.id],
    queryFn: () => fetchSlots(previousPeriod!.id),
    enabled: Boolean(previousPeriod),
  });

  const previousDetailQuery = useQuery({
    queryKey: ["availability-detail", previousPeriod?.id, user?.id],
    queryFn: () => fetchAvailability(previousPeriod!.id, user!.id),
    enabled: Boolean(previousPeriod && user),
  });

  if (periodsQuery.isLoading || shiftTypesQuery.isLoading || !user) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  if (periodsQuery.isError || shiftTypesQuery.isError) {
    return <ApiErrorText error={periodsQuery.error ?? shiftTypesQuery.error} />;
  }

  if (!periodsQuery.data || periodsQuery.data.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("availability.noPeriods")}</p>;
  }

  if (!selectedPeriodId || !selectedPeriod) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  const previousStatusBySlotId: Record<string, AvailabilityStatus> | null = previousDetailQuery.data
    ? Object.fromEntries(previousDetailQuery.data.entries.map((e) => [e.shift_slot_id, e.status]))
    : null;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("availability.title")}</h1>

      <PeriodSelector
        periods={periodsQuery.data}
        selectedPeriodId={selectedPeriodId}
        onChange={setSelectedPeriodId}
      />

      {(slotsQuery.isLoading || detailQuery.isLoading) && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}

      {(slotsQuery.isError || detailQuery.isError) && (
        <ApiErrorText error={slotsQuery.error ?? detailQuery.error} />
      )}

      {slotsQuery.data && detailQuery.data && shiftTypesQuery.data && (
        <AvailabilityCalendar
          key={selectedPeriodId}
          periodId={selectedPeriodId}
          userId={user.id}
          editable={
            selectedPeriod.state === "COLLECTING" ||
            (selectedPeriod.state === "LOCKED" && detailQuery.data.submission.reopened_by_manager)
          }
          readOnlyMessageKey={
            selectedPeriod.state === "LOCKED" && detailQuery.data.submission.reopened_by_manager
              ? null
              : READ_ONLY_KEY_BY_STATE[selectedPeriod.state] || null
          }
          reopenedNotice={
            selectedPeriod.state === "LOCKED" && detailQuery.data.submission.reopened_by_manager
          }
          slots={slotsQuery.data}
          shiftTypes={shiftTypesQuery.data}
          initialEntries={detailQuery.data.entries}
          initialValidation={detailQuery.data.validation}
          initialSubmissionStatus={detailQuery.data.submission.status}
          previousSlots={previousSlotsQuery.data ?? null}
          previousStatusBySlotId={previousStatusBySlotId}
        />
      )}
    </div>
  );
}

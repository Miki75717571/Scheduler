import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { SchedulePeriod } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { fetchShiftTypes, fetchSlots } from "../features/availability/api";
import { fetchPeriods } from "../features/manager/api";
import { fetchAssignments } from "../features/schedule/api";
import { EmployeeScheduleView } from "../features/schedule/EmployeeScheduleView";
import { useAuth } from "../lib/auth-context";

function monthLabel(period: SchedulePeriod, language: string): string {
  return new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    month: "long",
    year: "numeric",
  }).format(new Date(period.year, period.month - 1, 1));
}

function latestPublished(periods: SchedulePeriod[]): SchedulePeriod | null {
  const published = periods.filter((p) => p.state === "PUBLISHED");
  if (published.length === 0) return null;
  return [...published].sort((a, b) => b.year - a.year || b.month - a.month)[0];
}

export function EmployeeSchedulePage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null);

  const periodsQuery = useQuery({ queryKey: ["periods"], queryFn: fetchPeriods });
  const shiftTypesQuery = useQuery({ queryKey: ["shift-types"], queryFn: fetchShiftTypes });

  const publishedPeriods = (periodsQuery.data ?? []).filter((p) => p.state === "PUBLISHED");

  useEffect(() => {
    if (selectedPeriodId || !periodsQuery.data) return;
    const defaultPeriod = latestPublished(periodsQuery.data);
    if (defaultPeriod) setSelectedPeriodId(defaultPeriod.id);
  }, [periodsQuery.data, selectedPeriodId]);

  const slotsQuery = useQuery({
    queryKey: ["period-slots", selectedPeriodId],
    queryFn: () => fetchSlots(selectedPeriodId as string),
    enabled: Boolean(selectedPeriodId),
  });
  const assignmentsQuery = useQuery({
    queryKey: ["own-assignments", selectedPeriodId],
    queryFn: () => fetchAssignments(selectedPeriodId as string),
    enabled: Boolean(selectedPeriodId),
  });

  if (periodsQuery.isLoading || shiftTypesQuery.isLoading || !user) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (periodsQuery.isError || shiftTypesQuery.isError) {
    return <ApiErrorText error={periodsQuery.error ?? shiftTypesQuery.error} />;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("employeeSchedule.title")}</h1>

      {publishedPeriods.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("employeeSchedule.noPublishedPeriod")}</p>
      )}

      {publishedPeriods.length > 0 && selectedPeriodId && (
        <>
          {publishedPeriods.length > 1 && (
            <div className="space-y-1">
              <label htmlFor="employee-schedule-period" className="text-xs font-medium text-muted-foreground">
                {t("employeeSchedule.periodLabel")}
              </label>
              <select
                id="employee-schedule-period"
                value={selectedPeriodId}
                onChange={(event) => setSelectedPeriodId(event.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {[...publishedPeriods]
                  .sort((a, b) => b.year - a.year || b.month - a.month)
                  .map((period) => (
                    <option key={period.id} value={period.id}>
                      {monthLabel(period, i18n.language)}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {(slotsQuery.isLoading || assignmentsQuery.isLoading) && (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          )}
          {(slotsQuery.isError || assignmentsQuery.isError) && (
            <ApiErrorText error={slotsQuery.error ?? assignmentsQuery.error} />
          )}
          {slotsQuery.data && assignmentsQuery.data && shiftTypesQuery.data && (
            <EmployeeScheduleView
              key={selectedPeriodId}
              ownUserId={user.id}
              slots={slotsQuery.data}
              shiftTypes={shiftTypesQuery.data}
              assignments={assignmentsQuery.data}
            />
          )}
        </>
      )}
    </div>
  );
}

import { useTranslation } from "react-i18next";

import type { SchedulePeriod } from "../../api/types";
import { countdownTo } from "../../lib/countdown";

interface PeriodSelectorProps {
  periods: SchedulePeriod[];
  selectedPeriodId: string;
  onChange: (periodId: string) => void;
}

function monthLabel(period: SchedulePeriod, language: string): string {
  const formatter = new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    month: "long",
    year: "numeric",
  });
  return formatter.format(new Date(period.year, period.month - 1, 1));
}

export function PeriodSelector({ periods, selectedPeriodId, onChange }: PeriodSelectorProps) {
  const { t, i18n } = useTranslation();
  const selected = periods.find((p) => p.id === selectedPeriodId);
  const countdown = selected ? countdownTo(selected.availability_deadline) : { kind: "none" as const };

  return (
    <div className="space-y-1">
      <label htmlFor="period-select" className="text-xs font-medium text-muted-foreground">
        {t("availability.periodLabel")}
      </label>
      <select
        id="period-select"
        value={selectedPeriodId}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
      >
        {periods.map((period) => (
          <option key={period.id} value={period.id}>
            {monthLabel(period, i18n.language)} · {t(`manager.stateLabel.${period.state}`)}
          </option>
        ))}
      </select>
      {selected && (
        <p className="text-xs text-muted-foreground">
          {selected.availability_deadline
            ? t("availability.deadline", {
                date: new Date(selected.availability_deadline).toLocaleString(
                  i18n.language === "pl" ? "pl-PL" : "en-US",
                  { dateStyle: "medium", timeStyle: "short" },
                ),
              })
            : t("availability.deadlineNone")}
          {countdown.kind === "days" && (
            <span className="ml-2 font-medium text-amber-700">
              {t("availability.countdownDays", { count: countdown.count })}
            </span>
          )}
          {countdown.kind === "hours" && (
            <span className="ml-2 font-medium text-rose-700">
              {t("availability.countdownHours", { count: countdown.count })}
            </span>
          )}
          {countdown.kind === "passed" && (
            <span className="ml-2 font-medium text-rose-700">
              {t("availability.countdownPassed")}
            </span>
          )}
        </p>
      )}
    </div>
  );
}

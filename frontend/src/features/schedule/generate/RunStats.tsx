import { useTranslation } from "react-i18next";

import type { ScheduleRun } from "../../../api/types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

interface RunStatsProps {
  run: ScheduleRun;
  nameById: Record<string, string>;
}

// The at-a-glance summary from the task brief: "coverage %, preference
// satisfaction rate, fairness spread, and a per-employee shift count so I
// can see at a glance if someone got eight shifts and someone else two."
export function RunStats({ run, nameById }: RunStatsProps) {
  const { t } = useTranslation();
  const stats = run.stats;
  if (!stats) return null;

  const perEmployee = Object.entries(stats.shifts_per_employee)
    .map(([userId, count]) => ({ userId, name: nameById[userId] ?? userId, count }))
    .sort((a, b) => b.count - a.count);
  const maxCount = perEmployee.length > 0 ? perEmployee[0].count : 0;

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <h3 className="text-sm font-semibold">{t("generate.statsTitle")}</h3>

      <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">{t("generate.statsCoverage")}</dt>
          <dd className="font-medium">{pct(stats.coverage_rate)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("generate.statsPreference")}</dt>
          <dd className="font-medium">
            {stats.preference_satisfaction_rate === null
              ? t("generate.statsNoPreferences")
              : pct(stats.preference_satisfaction_rate)}
          </dd>
        </div>
        <div title={t("generate.statsFairnessSpreadHint")}>
          <dt className="text-xs text-muted-foreground">{t("generate.statsFairnessSpread")}</dt>
          <dd className="font-medium">{stats.fairness_spread}</dd>
        </div>
      </dl>

      <div>
        <h4 className="mb-1 text-xs font-semibold text-muted-foreground">
          {t("generate.statsShiftsPerEmployee")}
        </h4>
        <ul className="space-y-1">
          {perEmployee.map((entry) => (
            <li key={entry.userId} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 truncate" title={entry.name}>
                {entry.name}
              </span>
              <div className="h-2 flex-1 rounded bg-secondary">
                <div
                  className="h-2 rounded bg-primary"
                  style={{ width: maxCount > 0 ? `${(entry.count / maxCount) * 100}%` : "0%" }}
                />
              </div>
              <span className="w-4 shrink-0 text-right font-medium">{entry.count}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-muted-foreground">
        {t("generate.objectiveValue", {
          value: run.objective_value === null ? "—" : Math.round(run.objective_value),
        })}
        {" · "}
        {t("generate.solveTime", { ms: run.solve_time_ms ?? 0 })}
        {" · "}
        {t("generate.algorithmVersion", { version: run.algorithm_version })}
      </p>
    </div>
  );
}

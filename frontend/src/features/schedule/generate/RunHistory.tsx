import { useTranslation } from "react-i18next";

import type { ScheduleRun } from "../../../api/types";
import { cn } from "../../../lib/utils";

interface RunHistoryProps {
  runs: ScheduleRun[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

function formatWhen(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language === "pl" ? "pl-PL" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function direction(delta: number, t: (key: string) => string): string {
  if (delta > 0.0001) return t("generate.compareBetter");
  if (delta < -0.0001) return t("generate.compareWorse");
  return t("generate.compareSame");
}

// "Let me compare the current run against the previous one" - runs are
// already returned newest-first (ScheduleRunRepository.list_by_period), so
// the entry right after the selected one in this list is always "the
// previous run" for that comparison.
export function RunHistory({ runs, selectedRunId, onSelect }: RunHistoryProps) {
  const { t, i18n } = useTranslation();

  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("generate.historyEmpty")}</p>;
  }

  const selectedIndex = runs.findIndex((r) => r.id === selectedRunId);
  const selected = selectedIndex >= 0 ? runs[selectedIndex] : null;
  const previous = selectedIndex >= 0 ? (runs[selectedIndex + 1] ?? null) : null;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{t("generate.historyTitle")}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="py-1 pr-2 font-medium">{t("generate.historyColumnWhen")}</th>
              <th className="py-1 pr-2 font-medium">{t("generate.historyColumnStatus")}</th>
              <th className="py-1 pr-2 font-medium">{t("generate.historyColumnObjective")}</th>
              <th className="py-1 pr-2 font-medium">{t("generate.historyColumnSolveTime")}</th>
              <th className="py-1" />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                className={cn("border-t border-border", run.id === selectedRunId && "bg-secondary")}
              >
                <td className="py-1 pr-2">{formatWhen(run.created_at, i18n.language)}</td>
                <td className="py-1 pr-2">
                  {t(`generate.runStatus.${run.status}`)}
                  {run.reverted_at && (
                    <span className="ml-1 text-muted-foreground">
                      ·{" "}
                      {t("generate.revertedBadge", {
                        date: formatWhen(run.reverted_at, i18n.language),
                      })}
                    </span>
                  )}
                </td>
                <td className="py-1 pr-2">
                  {run.objective_value === null ? "—" : Math.round(run.objective_value)}
                </td>
                <td className="py-1 pr-2">
                  {run.solve_time_ms === null ? "—" : `${run.solve_time_ms}ms`}
                </td>
                <td className="py-1">
                  <button
                    type="button"
                    onClick={() => onSelect(run.id)}
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    {t("generate.historyViewButton")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected?.stats && previous?.stats && (
        <div className="rounded-md border border-border bg-secondary/50 p-2 text-xs">
          <p className="mb-1 font-semibold">{t("generate.compareTitle")}</p>
          <ul className="space-y-0.5">
            <li>
              {t("generate.compareCoverage", {
                value: `${Math.round(selected.stats.coverage_rate * 100)}% vs ${Math.round(previous.stats.coverage_rate * 100)}% (${direction(selected.stats.coverage_rate - previous.stats.coverage_rate, t)})`,
              })}
            </li>
            {selected.stats.preference_satisfaction_rate !== null &&
              previous.stats.preference_satisfaction_rate !== null && (
                <li>
                  {t("generate.comparePreference", {
                    value: `${Math.round(selected.stats.preference_satisfaction_rate * 100)}% vs ${Math.round(previous.stats.preference_satisfaction_rate * 100)}% (${direction(selected.stats.preference_satisfaction_rate - previous.stats.preference_satisfaction_rate, t)})`,
                  })}
                </li>
              )}
            <li>
              {t("generate.compareFairness", {
                value: `${selected.stats.fairness_spread} vs ${previous.stats.fairness_spread} (${direction(previous.stats.fairness_spread - selected.stats.fairness_spread, t)})`,
              })}
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}

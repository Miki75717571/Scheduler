import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ScoreCriterion, ScoreGridRow } from "../../api/types";
import { Button } from "../../components/ui/button";
import { cn } from "../../lib/utils";

type CellStatus = "idle" | "saving" | "saved" | "error";

interface ScoringGridProps {
  criteria: ScoreCriterion[];
  rows: ScoreGridRow[];
  onSetScore: (userId: string, criterionId: string, value: number) => Promise<void>;
  onOpenHistory: (userId: string, fullName: string) => void;
}

function cellKey(userId: string, criterionId: string): string {
  return `${userId}:${criterionId}`;
}

export function ScoringGrid({ criteria, rows, onSetScore, onOpenHistory }: ScoringGridProps) {
  const { t, i18n } = useTranslation();
  const [statusByCell, setStatusByCell] = useState<Record<string, CellStatus>>({});

  async function handleClick(userId: string, criterionId: string, value: number) {
    const key = cellKey(userId, criterionId);
    setStatusByCell((prev) => ({ ...prev, [key]: "saving" }));
    try {
      await onSetScore(userId, criterionId, value);
      setStatusByCell((prev) => ({ ...prev, [key]: "saved" }));
    } catch {
      setStatusByCell((prev) => ({ ...prev, [key]: "error" }));
    }
  }

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("scores.noEmployees")}</p>;
  }
  if (criteria.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("scores.noCriteria")}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-secondary text-secondary-foreground">
          <tr>
            <th className="sticky left-0 bg-secondary px-3 py-2">{t("scores.columnEmployee")}</th>
            {criteria.map((criterion) => (
              <th key={criterion.id} className="px-3 py-2 text-center">
                {i18n.language === "pl" ? criterion.name_pl : criterion.name_en}
              </th>
            ))}
            <th className="px-3 py-2 text-center">{t("scores.columnComposite")}</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const entryByCriterion = Object.fromEntries(
              row.entries.map((entry) => [entry.criterion_id, entry]),
            );
            return (
              <tr key={row.user_id} className="border-t border-border align-top">
                <td className="sticky left-0 whitespace-nowrap bg-background px-3 py-2 font-medium">
                  {row.full_name}
                </td>
                {criteria.map((criterion) => {
                  const entry = entryByCriterion[criterion.id];
                  const key = cellKey(row.user_id, criterion.id);
                  const status = statusByCell[key] ?? "idle";
                  return (
                    <td key={criterion.id} className="px-2 py-2">
                      <div
                        className="flex items-center justify-center gap-1"
                        role="group"
                        aria-label={t("scores.cellLabel", {
                          criterion: i18n.language === "pl" ? criterion.name_pl : criterion.name_en,
                          employee: row.full_name,
                        })}
                      >
                        {Array.from(
                          { length: criterion.scale_max - criterion.scale_min + 1 },
                          (_, i) => criterion.scale_min + i,
                        ).map((value) => (
                          <button
                            key={value}
                            type="button"
                            disabled={status === "saving"}
                            onClick={() => void handleClick(row.user_id, criterion.id, value)}
                            className={cn(
                              "h-6 w-6 rounded border text-xs leading-none",
                              entry?.value === value
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-background hover:bg-secondary",
                            )}
                          >
                            {value}
                          </button>
                        ))}
                      </div>
                      <p className="mt-1 text-center text-[11px] text-muted-foreground">
                        {status === "saving" && t("scores.savingIndicator")}
                        {status === "saved" && t("scores.savedIndicator")}
                        {status === "error" && (
                          <span className="text-destructive">{t("scores.saveErrorIndicator")}</span>
                        )}
                        {status === "idle" && entry === undefined && t("scores.notRated")}
                      </p>
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-center font-semibold">
                  {row.composite === null ? t("scores.compositeNotRated") : row.composite}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => onOpenHistory(row.user_id, row.full_name)}
                  >
                    {t("scores.historyButton")}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

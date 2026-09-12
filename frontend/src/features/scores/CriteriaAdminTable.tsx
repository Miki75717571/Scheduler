import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ScoreCriterion } from "../../api/types";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { cn } from "../../lib/utils";

interface WeightDraft {
  weight: string;
  is_active: boolean;
}

interface CriteriaAdminTableProps {
  criteria: ScoreCriterion[];
  onSaveWeights: (items: { id: string; weight: string; is_active: boolean }[]) => Promise<void>;
  onRename: (
    id: string,
    payload: { name_pl: string; name_en: string; description: string | null },
  ) => Promise<void>;
}

function sumActiveWeights(criteria: ScoreCriterion[], drafts: Record<string, WeightDraft>): number {
  return criteria.reduce((total, c) => {
    const draft = drafts[c.id];
    if (!draft.is_active) return total;
    const parsed = Number(draft.weight);
    return total + (Number.isFinite(parsed) ? parsed : 0);
  }, 0);
}

export function CriteriaAdminTable({ criteria, onSaveWeights, onRename }: CriteriaAdminTableProps) {
  const { t } = useTranslation();
  const [weightDrafts, setWeightDrafts] = useState<Record<string, WeightDraft>>(() =>
    Object.fromEntries(criteria.map((c) => [c.id, { weight: c.weight, is_active: c.is_active }])),
  );
  const [nameDrafts, setNameDrafts] = useState<
    Record<string, { name_pl: string; name_en: string; description: string }>
  >(() =>
    Object.fromEntries(
      criteria.map((c) => [
        c.id,
        { name_pl: c.name_pl, name_en: c.name_en, description: c.description ?? "" },
      ]),
    ),
  );
  const [weightsStatus, setWeightsStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [nameStatus, setNameStatus] = useState<
    Record<string, "idle" | "saving" | "saved" | "error">
  >({});

  const total = sumActiveWeights(criteria, weightDrafts);
  // Compare to 1 with a small epsilon: this is a live UI hint, not the
  // authoritative check - the server re-validates the exact Decimal sum.
  const totalIsValid = Math.abs(total - 1) < 0.001;

  function updateWeightDraft(id: string, patch: Partial<WeightDraft>) {
    setWeightDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
    setWeightsStatus("idle");
  }

  async function handleSaveWeights() {
    setWeightsStatus("saving");
    try {
      await onSaveWeights(
        criteria.map((c) => ({
          id: c.id,
          weight: weightDrafts[c.id].weight,
          is_active: weightDrafts[c.id].is_active,
        })),
      );
      setWeightsStatus("saved");
    } catch {
      setWeightsStatus("error");
    }
  }

  async function handleSaveName(id: string) {
    setNameStatus((prev) => ({ ...prev, [id]: "saving" }));
    try {
      const draft = nameDrafts[id];
      await onRename(id, {
        name_pl: draft.name_pl,
        name_en: draft.name_en,
        description: draft.description || null,
      });
      setNameStatus((prev) => ({ ...prev, [id]: "saved" }));
    } catch {
      setNameStatus((prev) => ({ ...prev, [id]: "error" }));
    }
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead className="bg-secondary text-secondary-foreground">
            <tr>
              <th className="px-2 py-2">{t("criteria.columnCode")}</th>
              <th className="px-2 py-2">{t("criteria.columnNamePl")}</th>
              <th className="px-2 py-2">{t("criteria.columnNameEn")}</th>
              <th className="px-2 py-2">{t("criteria.columnDescription")}</th>
              <th className="px-2 py-2">{t("criteria.columnScale")}</th>
              <th className="px-2 py-2">{t("criteria.columnWeight")}</th>
              <th className="px-2 py-2 text-center">{t("criteria.columnActive")}</th>
              <th className="px-2 py-2">{t("criteria.columnActions")}</th>
            </tr>
          </thead>
          <tbody>
            {criteria.map((criterion) => {
              const nameDraft = nameDrafts[criterion.id];
              const weightDraft = weightDrafts[criterion.id];
              const rowNameStatus = nameStatus[criterion.id] ?? "idle";
              return (
                <tr key={criterion.id} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-2 py-2 font-mono text-xs">
                    {criterion.code}
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      className="h-8 w-36"
                      value={nameDraft.name_pl}
                      onChange={(e) =>
                        setNameDrafts((prev) => ({
                          ...prev,
                          [criterion.id]: { ...prev[criterion.id], name_pl: e.target.value },
                        }))
                      }
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      className="h-8 w-36"
                      value={nameDraft.name_en}
                      onChange={(e) =>
                        setNameDrafts((prev) => ({
                          ...prev,
                          [criterion.id]: { ...prev[criterion.id], name_en: e.target.value },
                        }))
                      }
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      className="h-8 w-48"
                      value={nameDraft.description}
                      onChange={(e) =>
                        setNameDrafts((prev) => ({
                          ...prev,
                          [criterion.id]: { ...prev[criterion.id], description: e.target.value },
                        }))
                      }
                    />
                  </td>
                  <td className="whitespace-nowrap px-2 py-2 text-muted-foreground">
                    {criterion.scale_min}–{criterion.scale_max}
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      className="h-8 w-24"
                      value={weightDraft.weight}
                      onChange={(e) => updateWeightDraft(criterion.id, { weight: e.target.value })}
                    />
                  </td>
                  <td className="px-2 py-2 text-center">
                    <input
                      type="checkbox"
                      aria-label={t("criteria.columnActive")}
                      checked={weightDraft.is_active}
                      onChange={(e) =>
                        updateWeightDraft(criterion.id, { is_active: e.target.checked })
                      }
                    />
                  </td>
                  <td className="whitespace-nowrap px-2 py-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={rowNameStatus === "saving"}
                      onClick={() => void handleSaveName(criterion.id)}
                    >
                      {t("common.save")}
                    </Button>
                    {rowNameStatus === "saved" && (
                      <p className="mt-1 text-xs text-emerald-700">{t("scores.savedIndicator")}</p>
                    )}
                    {rowNameStatus === "error" && (
                      <p className="mt-1 text-xs text-destructive">
                        {t("scores.saveErrorIndicator")}
                      </p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={() => void handleSaveWeights()}
          disabled={weightsStatus === "saving"}
        >
          {t("criteria.saveWeightsButton")}
        </Button>
        <p className={cn("text-sm", totalIsValid ? "text-emerald-700" : "text-destructive")}>
          {t("criteria.runningTotal", { total: total.toFixed(4) })}{" "}
          {totalIsValid ? t("criteria.runningTotalValid") : t("criteria.runningTotalInvalid")}
        </p>
        {weightsStatus === "saved" && (
          <span className="text-sm text-emerald-700">{t("criteria.weightsSaved")}</span>
        )}
        {weightsStatus === "error" && (
          <span className="text-sm text-destructive">{t("scores.saveErrorIndicator")}</span>
        )}
      </div>
    </div>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { SolverWeightsValues } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { fetchSolverWeights, updateSolverWeights } from "../features/schedule/generate/api";
import {
  DEFAULT_SOLVER_WEIGHTS,
  SOLVER_WEIGHT_FIELDS,
} from "../features/schedule/generate/weightFields";

// The plain-language weight tuning screen the task brief asked for: "I am
// not going to remember what these mean in six months." Every field pairs
// its raw name (kept only as the API's contract) with a label and help text
// that says what turning it up actually does - never "W_FAIR" alone.
export function AdminSolverWeightsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<SolverWeightsValues | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  const weightsQuery = useQuery({ queryKey: ["solver-weights"], queryFn: fetchSolverWeights });

  useEffect(() => {
    if (weightsQuery.data && values === null) {
      setValues(weightsQuery.data);
    }
  }, [weightsQuery.data, values]);

  async function handleSave() {
    if (!values) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const updated = await updateSolverWeights(values);
      setValues(updated);
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: ["solver-weights"] });
    } catch (error) {
      setSaveError(error);
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    setValues(DEFAULT_SOLVER_WEIGHTS);
    setSaved(false);
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("solverWeights.title")}</h1>
      <p className="text-sm text-muted-foreground">{t("solverWeights.intro")}</p>

      {weightsQuery.isLoading && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {weightsQuery.error !== null && weightsQuery.error !== undefined && (
        <ApiErrorText error={weightsQuery.error} />
      )}

      {values && (
        <div className="space-y-4">
          <div className="space-y-4">
            {SOLVER_WEIGHT_FIELDS.map((field) => (
              <div key={field} className="space-y-1">
                <Label htmlFor={`weight-${field}`}>
                  {t(`solverWeights.fields.${field}.label`)}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t(`solverWeights.fields.${field}.help`)}
                </p>
                <Input
                  id={`weight-${field}`}
                  type="number"
                  min={0}
                  max={1_000_000}
                  className="h-9 w-32"
                  value={values[field]}
                  onChange={(e) =>
                    setValues((prev) =>
                      prev ? { ...prev, [field]: Number(e.target.value) || 0 } : prev,
                    )
                  }
                />
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
            <Button type="button" disabled={saving} onClick={() => void handleSave()}>
              {t("solverWeights.saveButton")}
            </Button>
            <Button type="button" variant="secondary" onClick={handleReset}>
              {t("solverWeights.resetButton")}
            </Button>
            {saved && <span className="text-sm text-emerald-700">{t("solverWeights.saved")}</span>}
          </div>
          {saveError !== null && <ApiErrorText error={saveError} />}
        </div>
      )}
    </div>
  );
}

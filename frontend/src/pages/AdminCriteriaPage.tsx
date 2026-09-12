import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { CriteriaAdminTable } from "../features/scores/CriteriaAdminTable";
import {
  createScoreCriterion,
  fetchScoreCriteria,
  updateScoreCriterion,
  updateScoreWeights,
} from "../features/scores/api";

const EMPTY_DRAFT = { code: "", name_pl: "", name_en: "" };

export function AdminCriteriaPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [newCriterion, setNewCriterion] = useState(EMPTY_DRAFT);
  const [addError, setAddError] = useState<unknown>(null);
  const [addSuccess, setAddSuccess] = useState(false);

  const criteriaQuery = useQuery({
    queryKey: ["score-criteria", { activeOnly: false }],
    queryFn: () => fetchScoreCriteria(false),
  });

  async function handleSaveWeights(items: { id: string; weight: string; is_active: boolean }[]) {
    await updateScoreWeights(items);
    await queryClient.invalidateQueries({ queryKey: ["score-criteria"] });
  }

  async function handleRename(
    id: string,
    payload: { name_pl: string; name_en: string; description: string | null },
  ) {
    await updateScoreCriterion(id, payload);
    await queryClient.invalidateQueries({ queryKey: ["score-criteria"] });
  }

  async function handleAddCriterion() {
    setAddError(null);
    setAddSuccess(false);
    try {
      await createScoreCriterion({
        code: newCriterion.code,
        name_pl: newCriterion.name_pl,
        name_en: newCriterion.name_en,
        description: null,
        weight: "0",
        is_active: false,
      });
      setNewCriterion(EMPTY_DRAFT);
      setAddSuccess(true);
      await queryClient.invalidateQueries({ queryKey: ["score-criteria"] });
    } catch (error) {
      setAddError(error);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("criteria.title")}</h1>

      {criteriaQuery.isLoading && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {criteriaQuery.isError && <ApiErrorText error={criteriaQuery.error} />}

      {criteriaQuery.data && (
        <CriteriaAdminTable
          criteria={criteriaQuery.data}
          onSaveWeights={handleSaveWeights}
          onRename={handleRename}
        />
      )}

      <section className="space-y-2 border-t border-border pt-4">
        <h2 className="text-sm font-semibold">{t("criteria.addButton")}</h2>
        <div className="flex flex-wrap items-end gap-2">
          <Input
            placeholder={t("criteria.newCode")}
            className="h-9 w-32"
            value={newCriterion.code}
            onChange={(e) => setNewCriterion((prev) => ({ ...prev, code: e.target.value }))}
          />
          <Input
            placeholder={t("criteria.newNamePl")}
            className="h-9 w-40"
            value={newCriterion.name_pl}
            onChange={(e) => setNewCriterion((prev) => ({ ...prev, name_pl: e.target.value }))}
          />
          <Input
            placeholder={t("criteria.newNameEn")}
            className="h-9 w-40"
            value={newCriterion.name_en}
            onChange={(e) => setNewCriterion((prev) => ({ ...prev, name_en: e.target.value }))}
          />
          <Button
            type="button"
            disabled={!newCriterion.code || !newCriterion.name_pl || !newCriterion.name_en}
            onClick={() => void handleAddCriterion()}
          >
            {t("criteria.addButton")}
          </Button>
        </div>
        {addSuccess && <p className="text-sm text-emerald-700">{t("criteria.createSuccess")}</p>}
        {addError !== null && <ApiErrorText error={addError} />}
      </section>
    </div>
  );
}

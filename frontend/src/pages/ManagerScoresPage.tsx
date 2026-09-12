import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiErrorText } from "../components/ApiErrorText";
import {
  fetchScoreCriteria,
  fetchScoreGrid,
  fetchScoreHistory,
  setEmployeeScore,
} from "../features/scores/api";
import { ScoreHistoryDialog } from "../features/scores/ScoreHistoryDialog";
import { ScoringGrid } from "../features/scores/ScoringGrid";

export function ManagerScoresPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [historyFor, setHistoryFor] = useState<{ userId: string; fullName: string } | null>(null);

  const criteriaQuery = useQuery({
    queryKey: ["score-criteria", { activeOnly: true }],
    queryFn: () => fetchScoreCriteria(true),
  });
  const gridQuery = useQuery({ queryKey: ["scores-grid"], queryFn: () => fetchScoreGrid() });
  const historyQuery = useQuery({
    queryKey: ["score-history", historyFor?.userId],
    queryFn: () => fetchScoreHistory(historyFor!.userId),
    enabled: historyFor !== null,
  });

  async function handleSetScore(userId: string, criterionId: string, value: number) {
    await setEmployeeScore(userId, { criterion_id: criterionId, value });
    await queryClient.invalidateQueries({ queryKey: ["scores-grid"] });
    await queryClient.invalidateQueries({ queryKey: ["score-history", userId] });
  }

  const loading = criteriaQuery.isLoading || gridQuery.isLoading;
  const error = criteriaQuery.error ?? gridQuery.error;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{t("scores.title")}</h1>

      {loading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
      {(criteriaQuery.isError || gridQuery.isError) && <ApiErrorText error={error} />}

      {criteriaQuery.data && gridQuery.data && (
        <ScoringGrid
          criteria={criteriaQuery.data}
          rows={gridQuery.data}
          onSetScore={handleSetScore}
          onOpenHistory={(userId, fullName) => setHistoryFor({ userId, fullName })}
        />
      )}

      {historyFor && (
        <ScoreHistoryDialog
          employeeName={historyFor.fullName}
          entries={historyQuery.data}
          loading={historyQuery.isLoading}
          error={historyQuery.error}
          onClose={() => setHistoryFor(null)}
        />
      )}
    </div>
  );
}

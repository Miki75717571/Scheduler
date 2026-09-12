import { apiClient } from "../../api/client";
import type { ScoreCriterion, ScoreEntry, ScoreGridRow, ScoreHistoryEntry } from "../../api/types";

export function fetchScoreCriteria(activeOnly = false): Promise<ScoreCriterion[]> {
  const query = activeOnly ? "?active_only=true" : "";
  return apiClient.get<ScoreCriterion[]>(`/score-criteria${query}`);
}

export function createScoreCriterion(payload: {
  code: string;
  name_pl: string;
  name_en: string;
  description: string | null;
  weight: string;
  is_active: boolean;
}): Promise<ScoreCriterion> {
  return apiClient.post<ScoreCriterion>("/score-criteria", payload);
}

export function updateScoreCriterion(
  criterionId: string,
  payload: Partial<Pick<ScoreCriterion, "name_pl" | "name_en" | "description">>,
): Promise<ScoreCriterion> {
  return apiClient.patch<ScoreCriterion>(`/score-criteria/${criterionId}`, payload);
}

export function deactivateScoreCriterion(criterionId: string): Promise<ScoreCriterion> {
  return apiClient.post<ScoreCriterion>(`/score-criteria/${criterionId}/deactivate`);
}

export function updateScoreWeights(
  items: { id: string; weight: string; is_active: boolean }[],
): Promise<ScoreCriterion[]> {
  return apiClient.put<ScoreCriterion[]>("/score-criteria/weights", { items });
}

export function fetchScoreGrid(asOf?: string): Promise<ScoreGridRow[]> {
  const query = asOf ? `?as_of=${asOf}` : "";
  return apiClient.get<ScoreGridRow[]>(`/scores/grid${query}`);
}

export function setEmployeeScore(
  userId: string,
  payload: { criterion_id: string; value: number; note?: string | null },
): Promise<ScoreEntry> {
  return apiClient.post<ScoreEntry>(`/users/${userId}/scores`, payload);
}

export function fetchScoreHistory(userId: string): Promise<ScoreHistoryEntry[]> {
  return apiClient.get<ScoreHistoryEntry[]>(`/users/${userId}/scores/history`);
}

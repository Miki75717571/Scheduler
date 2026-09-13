import { apiClient } from "../../../api/client";
import type { ScheduleRun, SolverWeights, SolverWeightsValues } from "../../../api/types";

export function createScheduleRun(periodId: string): Promise<ScheduleRun> {
  return apiClient.post<ScheduleRun>(`/periods/${periodId}/schedule-runs`, {});
}

export function fetchScheduleRuns(periodId: string): Promise<ScheduleRun[]> {
  return apiClient.get<ScheduleRun[]>(`/periods/${periodId}/schedule-runs`);
}

export function fetchScheduleRun(runId: string): Promise<ScheduleRun> {
  return apiClient.get<ScheduleRun>(`/schedule-runs/${runId}`);
}

export function revertScheduleRun(runId: string): Promise<ScheduleRun> {
  return apiClient.post<ScheduleRun>(`/schedule-runs/${runId}/revert`);
}

export function fetchSolverWeights(): Promise<SolverWeights> {
  return apiClient.get<SolverWeights>("/solver/weights");
}

export function updateSolverWeights(payload: SolverWeightsValues): Promise<SolverWeights> {
  return apiClient.put<SolverWeights>("/solver/weights", payload);
}

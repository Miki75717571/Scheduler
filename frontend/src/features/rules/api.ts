import { apiClient } from "../../api/client";
import type { Rule, RestConflict } from "../../api/types";

export function fetchRules(): Promise<Rule[]> {
  return apiClient.get<Rule[]>("/rules");
}

export function fetchRestConflicts(): Promise<RestConflict[]> {
  return apiClient.get<RestConflict[]>("/rules/rest-conflicts");
}

export function updateRuleParams(id: string, params: Record<string, unknown>): Promise<Rule> {
  return apiClient.patch<Rule>(`/rules/${id}`, { params });
}

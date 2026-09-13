import type { SolverWeightsValues } from "../../../api/types";

// Mirrors app/scheduling/domain.py's SolverWeights field defaults exactly -
// this is the client-side half of the admin "reset to defaults" button
// (ARCHITECTURE.md ss4.1). Order here is also the display order on the
// weights page: coverage first (the one thing that's never allowed to be
// hard), down to the two "soften the edges" terms at the bottom.
// Tuned for a ~7-person crew with one-person shifts (CLAUDE.md JOB 6c) -
// see the Python dataclass's docstring for the full rationale.
export const DEFAULT_SOLVER_WEIGHTS: SolverWeightsValues = {
  understaffing: 10000,
  contract_min_shortfall: 2500,
  denied_preference: 20,
  fairness_spread: 60,
  unpopular_shift_spread: 50,
  score_weight: 5,
  preference_debt: 15,
};

export const SOLVER_WEIGHT_FIELDS: (keyof SolverWeightsValues)[] = [
  "understaffing",
  "contract_min_shortfall",
  "denied_preference",
  "fairness_spread",
  "unpopular_shift_spread",
  "score_weight",
  "preference_debt",
];

export type Role = "EMPLOYEE" | "MANAGER" | "ADMIN";
export type EmploymentType = "FULL_TIME" | "PART_TIME" | "STUDENT" | "CASUAL";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  employment_type: EmploymentType | null;
  contract_min_shifts: number | null;
  contract_max_shifts: number | null;
  locale: string;
  is_active: boolean;
  created_at: string;
  invited_at: string | null;
  activated_at: string | null;
}

export type PeriodState = "DRAFT" | "COLLECTING" | "LOCKED" | "GENERATED" | "PUBLISHED";

export interface SchedulePeriod {
  id: string;
  year: number;
  month: number;
  state: PeriodState;
  availability_opens_at: string | null;
  availability_deadline: string | null;
  published_at: string | null;
  published_by_user_id: string | null;
  created_at: string;
}

export interface ShiftType {
  id: string;
  code: string;
  name_pl: string;
  name_en: string;
  start_time: string;
  end_time: string;
  color_hex: string;
  active_weekdays: number;
  default_required_staff: number;
  default_min_staff: number;
  default_max_staff: number;
  sort_order: number;
  is_active: boolean;
}

export interface ShiftSlot {
  id: string;
  period_id: string;
  date: string;
  shift_type_id: string;
  required_staff: number;
  min_staff: number;
  max_staff: number;
  is_closed: boolean;
  note: string | null;
}

export type AvailabilityStatus = "UNAVAILABLE" | "AVAILABLE" | "PREFERRED";
export type SubmissionStatus = "NOT_STARTED" | "DRAFT" | "SUBMITTED";

export interface AvailabilityEntry {
  shift_slot_id: string;
  status: AvailabilityStatus;
  note: string | null;
}

export interface AvailabilitySubmission {
  id: string;
  user_id: string;
  period_id: string;
  status: SubmissionStatus;
  submitted_at: string | null;
  last_edited_at: string | null;
  reopened_by_manager: boolean;
}

export interface RuleCheckResult {
  rule_code: string;
  severity: "HARD" | "SOFT";
  passed: boolean;
  message_key: string;
  message_params: Record<string, unknown>;
}

export interface AvailabilityDetail {
  submission: AvailabilitySubmission;
  entries: AvailabilityEntry[];
  validation: RuleCheckResult[];
}

export interface SubmissionTrackerEntry {
  user_id: string;
  full_name: string;
  employment_type: EmploymentType | null;
  status: SubmissionStatus;
  submitted_at: string | null;
  reopened_by_manager: boolean;
}

export type AssignmentSource = "AUTO" | "MANUAL";

export interface Assignment {
  id: string;
  shift_slot_id: string;
  user_id: string;
  full_name: string;
  source: AssignmentSource;
  is_locked: boolean;
  modified_after_publish: boolean;
  created_by_user_id: string;
  created_at: string;
  updated_at: string | null;
}

export type ViolationSeverity = "ERROR" | "WARNING";

export interface ScheduleViolation {
  severity: ViolationSeverity;
  rule_code: string;
  rule_type: string;
  message_key: string;
  message_params: Record<string, unknown>;
  shift_slot_id: string | null;
  user_id: string | null;
}

export interface AssignmentMutationResult {
  assignment: Assignment | null;
  violations: ScheduleViolation[];
}

export interface BulkAssignmentResult {
  assignments: Assignment[];
  violations: ScheduleViolation[];
}

export interface AvailableEmployee {
  user_id: string;
  full_name: string;
  status: AvailabilityStatus;
}

export interface ScoreCriterion {
  id: string;
  code: string;
  name_pl: string;
  name_en: string;
  description: string | null;
  weight: string; // exact Decimal, serialized as a string - never parse with Number() for comparisons
  scale_min: number;
  scale_max: number;
  is_active: boolean;
}

export interface ScoreEntry {
  criterion_id: string;
  value: number;
  effective_from: string;
  set_by_user_id: string;
  note: string | null;
}

export interface ScoreGridRow {
  user_id: string;
  full_name: string;
  entries: ScoreEntry[];
  composite: number | null;
}

export type AvailabilityLevel = "AVAILABLE" | "PREFERRED";

export interface UnusedAvailableEmployee {
  employee_id: string;
  full_name: string;
  level: AvailabilityLevel;
  message_key: string;
  message_params: Record<string, unknown>;
}

export interface SlotDiagnostic {
  slot_id: string;
  date: string;
  shift_type_code: string;
  required_staff: number;
  min_staff: number;
  assigned_staff: number;
  available_staff: number;
  message_key: string;
  message_params: Record<string, unknown>;
  unused_available: UnusedAvailableEmployee[];
}

export interface EmployeeDiagnostic {
  employee_id: string;
  assigned_count: number;
  contract_min_shifts: number;
  shortfall: number;
  declared_count: number;
  message_key: string;
  message_params: Record<string, unknown>;
}

export interface ScheduleDiagnostics {
  slots: SlotDiagnostic[];
  employees: EmployeeDiagnostic[];
}

export interface SolverStats {
  total_slots: number;
  total_required_staff: number;
  total_assigned: number;
  understaffed_slot_count: number;
  coverage_rate: number;
  preference_satisfaction_rate: number | null;
  fairness_spread: number;
  shifts_per_employee: Record<string, number>;
}

export type ScheduleRunStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";

export interface SolverWeightsValues {
  understaffing: number;
  contract_min_shortfall: number;
  denied_preference: number;
  fairness_spread: number;
  unpopular_shift_spread: number;
  score_weight: number;
  preference_debt: number;
}

export interface SolverWeights extends SolverWeightsValues {
  id: string;
  updated_at: string | null;
  updated_by_user_id: string | null;
}

export interface ScheduleRunParamsSnapshot {
  weights: SolverWeightsValues;
  time_limit_seconds: number;
  random_seed: number;
  num_search_workers: number;
}

export interface ScheduleRun {
  id: string;
  period_id: string;
  status: ScheduleRunStatus;
  algorithm_version: string;
  params_snapshot: ScheduleRunParamsSnapshot;
  objective_value: number | null;
  solve_time_ms: number | null;
  solver_status: string | null;
  stats: SolverStats | null;
  diagnostics: ScheduleDiagnostics | null;
  error_message: string | null;
  pre_run_snapshot: unknown[] | null;
  reverted_at: string | null;
  reverted_by_user_id: string | null;
  created_by_user_id: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ScoreHistoryEntry {
  id: string;
  criterion_id: string;
  criterion_code: string;
  criterion_name_pl: string;
  criterion_name_en: string;
  value: number;
  previous_value: number | null;
  effective_from: string;
  set_by_user_id: string;
  set_by_full_name: string;
  note: string | null;
  created_at: string;
}

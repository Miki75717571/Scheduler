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

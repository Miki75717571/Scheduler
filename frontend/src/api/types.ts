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

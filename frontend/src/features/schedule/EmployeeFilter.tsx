import { useTranslation } from "react-i18next";

interface RosterMember {
  user_id: string;
  full_name: string;
}

interface EmployeeFilterProps {
  roster: RosterMember[];
  selectedEmployeeId: string | null;
  shiftCount: number;
  onChange: (userId: string | null) => void;
}

export function EmployeeFilter({ roster, selectedEmployeeId, shiftCount, onChange }: EmployeeFilterProps) {
  const { t } = useTranslation();
  const sorted = [...roster].sort((a, b) => a.full_name.localeCompare(b.full_name));

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      <label htmlFor="schedule-employee-filter" className="text-xs font-medium text-muted-foreground">
        {t("schedule.filterLabel")}
      </label>
      <select
        id="schedule-employee-filter"
        value={selectedEmployeeId ?? ""}
        onChange={(event) => onChange(event.target.value || null)}
        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      >
        <option value="">{t("schedule.filterAll")}</option>
        {sorted.map((member) => (
          <option key={member.user_id} value={member.user_id}>
            {member.full_name}
          </option>
        ))}
      </select>
      {selectedEmployeeId && (
        <span className="text-xs text-muted-foreground">
          {t("schedule.filterShiftCount", { count: shiftCount })}
        </span>
      )}
    </div>
  );
}

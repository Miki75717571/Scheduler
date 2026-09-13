import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScheduleDiagnostics } from "../../../api/types";
import i18n from "../../../i18n";
import { RunDiagnostics } from "./RunDiagnostics";

const DIAGNOSTICS: ScheduleDiagnostics = {
  slots: [
    {
      slot_id: "slot-1",
      date: "2027-03-05",
      shift_type_code: "EVENING",
      required_staff: 2,
      min_staff: 1,
      assigned_staff: 1,
      available_staff: 2,
      message_key: "solver.slot_understaffed",
      message_params: {
        assigned_staff: 1,
        required_staff: 2,
        available_staff: 2,
        date: "2027-03-05",
        shift_type_code: "EVENING",
      },
      unused_available: [
        {
          employee_id: "u-busy",
          full_name: "Busy Employee",
          level: "AVAILABLE",
          message_key: "solver.unused_already_assigned_same_day",
          message_params: { shift_type_code: "MORNING" },
        },
        {
          employee_id: "u-capped",
          full_name: "Capped Employee",
          level: "PREFERRED",
          message_key: "solver.unused_contract_max_reached",
          message_params: { contract_max_shifts: 5 },
        },
      ],
    },
  ],
  employees: [
    {
      employee_id: "u-short",
      assigned_count: 3,
      contract_min_shifts: 5,
      shortfall: 2,
      declared_count: 4,
      message_key: "solver.employee_below_contract_min",
      message_params: {
        full_name: "Short Employee",
        assigned_count: 3,
        contract_min_shifts: 5,
        declared_count: 4,
        shortfall: 2,
      },
    },
  ],
  rest_conflicts: [],
};

describe("RunDiagnostics", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
  });

  it("shows the all-clear state when there are no issues", () => {
    render(
      <RunDiagnostics
        diagnostics={{ slots: [], employees: [], rest_conflicts: [] }}
        nameById={{}}
        shiftTypeNameByCode={{}}
      />,
    );
    expect(screen.getByText(/No understaffed shifts/)).toBeInTheDocument();
  });

  it("explains an understaffed slot and why each available person wasn't used", () => {
    render(
      <RunDiagnostics
        diagnostics={DIAGNOSTICS}
        nameById={{ "u-short": "Short Employee" }}
        shiftTypeNameByCode={{ EVENING: "Evening" }}
      />,
    );

    expect(screen.getByText(/Understaffed shifts \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/1\/2 staff assigned — 2 people were available/)).toBeInTheDocument();

    expect(screen.getByText("Busy Employee")).toBeInTheDocument();
    expect(screen.getByText(/Already working a MORNING shift that day/)).toBeInTheDocument();

    expect(screen.getByText("Capped Employee")).toBeInTheDocument();
    expect(screen.getByText(/Already at their contract maximum of 5 shifts/)).toBeInTheDocument();
  });

  it("explains an employee below their contract minimum", () => {
    render(
      <RunDiagnostics
        diagnostics={DIAGNOSTICS}
        nameById={{ "u-short": "Short Employee" }}
        shiftTypeNameByCode={{ EVENING: "Evening" }}
      />,
    );

    expect(screen.getByText(/Below contract minimum \(1\)/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Short Employee: 3\/5 shifts \(declared 4\) — 2 short of their contract minimum/,
      ),
    ).toBeInTheDocument();
  });

  it("shows a rest-rule conflict banner separate from per-slot diagnostics", () => {
    render(
      <RunDiagnostics
        diagnostics={{
          slots: [],
          employees: [],
          rest_conflicts: [
            {
              from_shift_type_code: "EVENING",
              from_weekday: "FRI",
              to_shift_type_code: "MORNING",
              to_weekday: "SAT",
              gap_hours: 10.5,
              required_hours: 11,
              message_key: "solver.rest_conflict",
              message_params: {
                from_shift_type_code: "EVENING",
                from_weekday: "FRI",
                to_shift_type_code: "MORNING",
                to_weekday: "SAT",
                gap_hours: 10.5,
                required_hours: 11,
              },
            },
          ],
        }}
        nameById={{}}
        shiftTypeNameByCode={{}}
      />,
    );

    expect(screen.getByText(/Rest-rule conflicts \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/FRI EVENING/)).toBeInTheDocument();
    expect(screen.getByText(/SAT MORNING/)).toBeInTheDocument();
  });

  it("jumps to the slot's date when clicked", async () => {
    const onJumpToDate = vi.fn();
    render(
      <RunDiagnostics
        diagnostics={DIAGNOSTICS}
        nameById={{}}
        shiftTypeNameByCode={{ EVENING: "Evening" }}
        onJumpToDate={onJumpToDate}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Evening/ }));
    expect(onJumpToDate).toHaveBeenCalledWith("2027-03-05");
  });
});

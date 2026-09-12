import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScheduleViolation } from "../../api/types";
import i18n from "../../i18n";
import { ViolationsPanel } from "./ViolationsPanel";

const ERROR_VIOLATION: ScheduleViolation = {
  severity: "ERROR",
  rule_code: "UNDERSTAFFING",
  rule_type: "UNDERSTAFFING",
  message_key: "schedule.understaffed_below_minimum",
  message_params: { assigned: 0, min_staff: 1, required_staff: 2 },
  shift_slot_id: "slot-1",
  user_id: null,
};

const WARNING_VIOLATION: ScheduleViolation = {
  severity: "WARNING",
  rule_code: "AVAILABILITY_MISMATCH",
  rule_type: "AVAILABILITY_MISMATCH",
  message_key: "schedule.assigned_despite_unavailable",
  message_params: {},
  shift_slot_id: "slot-2",
  user_id: "u-anna",
};

describe("ViolationsPanel", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
  });

  it("shows the all-clear state when there are no violations", () => {
    render(<ViolationsPanel violations={[]} nameById={{}} dateBySlotId={{}} onJump={vi.fn()} />);
    expect(screen.getByText(/no violations/i)).toBeInTheDocument();
  });

  it("groups violations by severity with a count in each heading", () => {
    render(
      <ViolationsPanel
        violations={[ERROR_VIOLATION, WARNING_VIOLATION]}
        nameById={{ "u-anna": "Anna Kowalska" }}
        dateBySlotId={{}}
        onJump={vi.fn()}
      />,
    );
    expect(screen.getByText("Errors (1)")).toBeInTheDocument();
    expect(screen.getByText("Warnings (1)")).toBeInTheDocument();
    expect(screen.getByText(/Only 0 staff scheduled, below the minimum of 1/)).toBeInTheDocument();
  });

  it("prefixes a violation with the employee's name when it names one", () => {
    render(
      <ViolationsPanel
        violations={[WARNING_VIOLATION]}
        nameById={{ "u-anna": "Anna Kowalska" }}
        dateBySlotId={{}}
        onJump={vi.fn()}
      />,
    );
    expect(screen.getByText(/Anna Kowalska:/)).toBeInTheDocument();
  });

  it("jumps using the slot's date when the violation names a shift slot", async () => {
    const onJump = vi.fn();
    render(
      <ViolationsPanel
        violations={[ERROR_VIOLATION]}
        nameById={{}}
        dateBySlotId={{ "slot-1": "2027-03-05" }}
        onJump={onJump}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByText(/Only 0 staff scheduled/));
    expect(onJump).toHaveBeenCalledWith({ date: "2027-03-05", userId: null });
  });

  it("falls back to the employee id when a violation has no slot or date", async () => {
    const onJump = vi.fn();
    const monthWide: ScheduleViolation = {
      severity: "ERROR",
      rule_code: "min_shifts",
      rule_type: "MIN_SHIFTS_PER_MONTH",
      message_key: "rules.MIN_SHIFTS_PER_MONTH",
      message_params: { required: 5, actual: 2 },
      shift_slot_id: null,
      user_id: "u-bob",
    };
    render(
      <ViolationsPanel
        violations={[monthWide]}
        nameById={{ "u-bob": "Bob Nowak" }}
        dateBySlotId={{}}
        onJump={onJump}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByText(/2\/5 shifts this month/));
    expect(onJump).toHaveBeenCalledWith({ date: null, userId: "u-bob" });
  });
});

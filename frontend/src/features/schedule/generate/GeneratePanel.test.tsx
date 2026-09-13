import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Assignment, ScheduleRun } from "../../../api/types";
import i18n from "../../../i18n";
import * as api from "./api";
import { GeneratePanel } from "./GeneratePanel";

vi.mock("./api");

function makeAssignment(overrides: Partial<Assignment> = {}): Assignment {
  return {
    id: `a-${Math.random()}`,
    shift_slot_id: "slot-1",
    user_id: "u-1",
    full_name: "Anna Kowalska",
    source: "MANUAL",
    is_locked: false,
    modified_after_publish: false,
    created_by_user_id: "mgr-1",
    created_at: "2027-03-01T00:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

function makeRun(overrides: Partial<ScheduleRun> = {}): ScheduleRun {
  return {
    id: "run-1",
    period_id: "period-1",
    status: "PENDING",
    algorithm_version: "cpsat-v1",
    params_snapshot: {
      weights: {
        understaffing: 10000,
        contract_min_shortfall: 1000,
        denied_preference: 20,
        fairness_spread: 30,
        unpopular_shift_spread: 25,
        score_weight: 10,
        preference_debt: 15,
      },
      time_limit_seconds: 30,
      random_seed: 42,
      num_search_workers: 8,
    },
    objective_value: null,
    solve_time_ms: null,
    solver_status: null,
    stats: null,
    diagnostics: null,
    error_message: null,
    pre_run_snapshot: [],
    reverted_at: null,
    reverted_by_user_id: null,
    created_by_user_id: "mgr-1",
    created_at: "2027-03-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

function renderPanel(assignments: Assignment[] = []) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <GeneratePanel
        periodId="period-1"
        periodState="LOCKED"
        assignments={assignments}
        nameById={{ "u-1": "Anna Kowalska" }}
        shiftTypeNameByCode={{ EVENING: "Evening" }}
      />
    </QueryClientProvider>,
  );
}

describe("GeneratePanel", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
    vi.mocked(api.fetchScheduleRuns).mockResolvedValue([]);
  });

  it("idle: disables the button with an explanation when the period isn't locked", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <GeneratePanel
          periodId="period-1"
          periodState="COLLECTING"
          assignments={[]}
          nameById={{}}
          shiftTypeNameByCode={{}}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("button", { name: "Generate schedule" })).not.toBeInTheDocument();
    expect(screen.getByText("Lock availability before generating a schedule.")).toBeInTheDocument();
  });

  it("idle: shows an enabled Generate button and the locked/discard confirmation when clicked", async () => {
    renderPanel([makeAssignment({ is_locked: true }), makeAssignment({ is_locked: false })]);
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: "Generate schedule" });
    expect(button).toBeEnabled();
    await user.click(button);

    expect(screen.getByText(/1 locked assignment\(s\) will be kept/)).toBeInTheDocument();
    expect(screen.getByText(/1 unlocked assignment\(s\) will be discarded/)).toBeInTheDocument();
  });

  it("running: shows a solving status once a run is created", async () => {
    vi.mocked(api.createScheduleRun).mockResolvedValue(makeRun({ status: "PENDING" }));
    vi.mocked(api.fetchScheduleRun).mockResolvedValue(makeRun({ status: "RUNNING" }));
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Generate schedule" }));
    await user.click(screen.getByRole("button", { name: "Generate" }));

    await waitFor(() =>
      expect(screen.getByText(/Solving… this can take up to 30s/)).toBeInTheDocument(),
    );
  });

  it("success: shows the success status plus results once the run completes", async () => {
    vi.mocked(api.createScheduleRun).mockResolvedValue(makeRun({ status: "PENDING" }));
    vi.mocked(api.fetchScheduleRun).mockResolvedValue(
      makeRun({
        status: "SUCCESS",
        objective_value: 123,
        solve_time_ms: 456,
        stats: {
          total_slots: 10,
          total_required_staff: 20,
          total_assigned: 18,
          understaffed_slot_count: 1,
          coverage_rate: 0.9,
          preference_satisfaction_rate: 0.5,
          fairness_spread: 2,
          shifts_per_employee: { "u-1": 4 },
        },
        diagnostics: { slots: [], employees: [], rest_conflicts: [] },
      }),
    );
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Generate schedule" }));
    await user.click(screen.getByRole("button", { name: "Generate" }));

    await waitFor(() => expect(screen.getByText("Schedule generated.")).toBeInTheDocument());
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("Anna Kowalska")).toBeInTheDocument();
  });

  it("failure: shows a readable error message rather than a spinner that never stops", async () => {
    vi.mocked(api.createScheduleRun).mockResolvedValue(makeRun({ status: "PENDING" }));
    vi.mocked(api.fetchScheduleRun).mockResolvedValue(
      makeRun({ status: "FAILED", error_message: "solver blew up" }),
    );
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Generate schedule" }));
    await user.click(screen.getByRole("button", { name: "Generate" }));

    await waitFor(() =>
      expect(screen.getByText("Generation failed: solver blew up")).toBeInTheDocument(),
    );
  });
});

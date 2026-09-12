import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScoreCriterion, ScoreGridRow } from "../../api/types";
import i18n from "../../i18n";
import { ScoringGrid } from "./ScoringGrid";

const RELIABILITY: ScoreCriterion = {
  id: "c-reliability",
  code: "RELIABILITY",
  name_pl: "Niezawodnosc",
  name_en: "Reliability",
  description: null,
  weight: "1.0000",
  scale_min: 1,
  scale_max: 5,
  is_active: true,
};

const ANNA_ROW: ScoreGridRow = {
  user_id: "u-anna",
  full_name: "Anna Kowalska",
  entries: [
    {
      criterion_id: "c-reliability",
      value: 4,
      effective_from: "2027-03-01",
      set_by_user_id: "u-mgr",
      note: null,
    },
  ],
  composite: 75,
};

describe("ScoringGrid", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
  });

  it("shows the currently-effective value and composite for each row", () => {
    render(
      <ScoringGrid
        criteria={[RELIABILITY]}
        rows={[ANNA_ROW]}
        onSetScore={vi.fn()}
        onOpenHistory={vi.fn()}
      />,
    );
    expect(screen.getByText("Anna Kowalska")).toBeInTheDocument();
    expect(screen.getByText("75")).toBeInTheDocument();
  });

  it("clicking a value calls onSetScore with that criterion and value", async () => {
    const onSetScore = vi.fn().mockResolvedValue(undefined);
    render(
      <ScoringGrid
        criteria={[RELIABILITY]}
        rows={[ANNA_ROW]}
        onSetScore={onSetScore}
        onOpenHistory={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    const group = screen.getByRole("group", { name: "Reliability for Anna Kowalska" });
    await user.click(within(group).getByRole("button", { name: "5" }));
    expect(onSetScore).toHaveBeenCalledWith("u-anna", "c-reliability", 5);
  });

  it("shows a not-yet-rated hint for an employee missing a value", () => {
    const unratedRow: ScoreGridRow = { ...ANNA_ROW, entries: [], composite: null };
    render(
      <ScoringGrid
        criteria={[RELIABILITY]}
        rows={[unratedRow]}
        onSetScore={vi.fn()}
        onOpenHistory={vi.fn()}
      />,
    );
    expect(screen.getByText("Not yet rated")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("opens history for the right employee", async () => {
    const onOpenHistory = vi.fn();
    render(
      <ScoringGrid
        criteria={[RELIABILITY]}
        rows={[ANNA_ROW]}
        onSetScore={vi.fn()}
        onOpenHistory={onOpenHistory}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(onOpenHistory).toHaveBeenCalledWith("u-anna", "Anna Kowalska");
  });
});

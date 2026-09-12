import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AvailableEmployee } from "../../api/types";
import i18n from "../../i18n";
import { AssignPickerDialog } from "./AssignPickerDialog";

const ROSTER = [
  { user_id: "u-anna", full_name: "Anna Kowalska" },
  { user_id: "u-bob", full_name: "Bob Nowak" },
  { user_id: "u-carla", full_name: "Carla Zielinska" },
  { user_id: "u-dan", full_name: "Dan Wisniewski" },
];

const CANDIDATES: AvailableEmployee[] = [
  { user_id: "u-bob", full_name: "Bob Nowak", status: "AVAILABLE" },
  { user_id: "u-anna", full_name: "Anna Kowalska", status: "PREFERRED" },
];

function renderDialog(overrides: Partial<React.ComponentProps<typeof AssignPickerDialog>> = {}) {
  const onPick = vi.fn();
  const onClose = vi.fn();
  render(
    <AssignPickerDialog
      shiftTypeName="Morning"
      dateLabel="1 Mar"
      roster={ROSTER}
      assignedUserIds={new Set()}
      candidates={CANDIDATES}
      loading={false}
      error={null}
      pendingUserId={null}
      onPick={onPick}
      onClose={onClose}
      {...overrides}
    />,
  );
  return { onPick, onClose };
}

describe("AssignPickerDialog", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
  });

  it("shows preferred candidates before available ones", () => {
    renderDialog();
    expect(screen.getByText("Preferred")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anna Kowalska/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bob Nowak/ })).toBeInTheDocument();
  });

  it("collapses the unavailable section by default, with a warning once expanded", async () => {
    renderDialog();
    // Carla and Dan aren't in `candidates`, so they fall into the collapsed
    // "not marked available" bucket.
    expect(screen.queryByText("Carla Zielinska")).not.toBeInTheDocument();
    expect(screen.getByText(/Not marked available \(2\)/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText(/Not marked available \(2\)/));

    expect(screen.getByText("Carla Zielinska")).toBeInTheDocument();
    expect(screen.getByText("Dan Wisniewski")).toBeInTheDocument();
    expect(screen.getByText(/hasn't declared themselves available/)).toBeInTheDocument();
  });

  it("excludes already-assigned employees from every section", async () => {
    renderDialog({ assignedUserIds: new Set(["u-anna", "u-carla"]) });
    expect(screen.queryByText("Anna Kowalska")).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText(/Not marked available \(1\)/));
    expect(screen.queryByText("Carla Zielinska")).not.toBeInTheDocument();
    expect(screen.getByText("Dan Wisniewski")).toBeInTheDocument();
  });

  it("calls onPick with the chosen user id", async () => {
    const { onPick } = renderDialog();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Bob Nowak/ }));
    expect(onPick).toHaveBeenCalledWith("u-bob");
  });

  it("closes on Escape", async () => {
    const { onClose } = renderDialog();
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("shows the no-candidates message when nobody at all is eligible", () => {
    renderDialog({ candidates: [], roster: [] });
    expect(screen.getByText("Nobody is available for this shift.")).toBeInTheDocument();
  });
});

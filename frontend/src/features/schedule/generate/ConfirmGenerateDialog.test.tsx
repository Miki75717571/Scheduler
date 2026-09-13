import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../../i18n";
import { ConfirmGenerateDialog } from "./ConfirmGenerateDialog";

describe("ConfirmGenerateDialog", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
  });

  it("shows how many assignments are locked (kept) and discarded", () => {
    render(
      <ConfirmGenerateDialog
        lockedCount={3}
        discardCount={7}
        pending={false}
        error={null}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/3 locked assignment\(s\) will be kept/)).toBeInTheDocument();
    expect(screen.getByText(/7 unlocked assignment\(s\) will be discarded/)).toBeInTheDocument();
  });

  it("shows a reassuring message when there is nothing to lose", () => {
    render(
      <ConfirmGenerateDialog
        lockedCount={0}
        discardCount={0}
        pending={false}
        error={null}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("There are no existing assignments to lose.")).toBeInTheDocument();
  });

  it("calls onConfirm when the manager confirms", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmGenerateDialog
        lockedCount={1}
        discardCount={1}
        pending={false}
        error={null}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("calls onCancel when the manager cancels or presses Escape", async () => {
    const onCancel = vi.fn();
    render(
      <ConfirmGenerateDialog
        lockedCount={0}
        discardCount={2}
        pending={false}
        error={null}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("disables the confirm and cancel buttons while pending", () => {
    render(
      <ConfirmGenerateDialog
        lockedCount={0}
        discardCount={2}
        pending
        error={null}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});

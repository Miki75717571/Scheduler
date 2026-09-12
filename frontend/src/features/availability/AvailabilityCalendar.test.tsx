import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AvailabilityDetail, ShiftSlot, ShiftType } from "../../api/types";
import i18n from "../../i18n";
import { AvailabilityCalendar } from "./AvailabilityCalendar";
import * as api from "./api";

vi.mock("./api");

const MORNING: ShiftType = {
  id: "morning",
  code: "MORNING",
  name_pl: "Rano",
  name_en: "Morning",
  start_time: "07:00:00",
  end_time: "15:00:00",
  color_hex: "#fbbf24",
  active_weekdays: 127,
  default_required_staff: 1,
  default_min_staff: 1,
  default_max_staff: 2,
  sort_order: 0,
  is_active: true,
};

const SLOT: ShiftSlot = {
  id: "slot-1",
  period_id: "period-1",
  date: "2027-03-01",
  shift_type_id: "morning",
  required_staff: 1,
  min_staff: 1,
  max_staff: 2,
  is_closed: false,
  note: null,
};

function detailWith(validation: AvailabilityDetail["validation"]): AvailabilityDetail {
  return {
    submission: {
      id: "sub-1",
      user_id: "user-1",
      period_id: "period-1",
      status: "DRAFT",
      submitted_at: null,
      last_edited_at: null,
      reopened_by_manager: false,
    },
    entries: [],
    validation,
  };
}

const PASSING_VALIDATION = [
  {
    rule_code: "min_1",
    severity: "HARD" as const,
    passed: true,
    message_key: "rules.MIN_AVAILABILITY_COUNT",
    message_params: { required: 1, actual: 1 },
  },
];

const FAILING_VALIDATION = [
  {
    rule_code: "min_1",
    severity: "HARD" as const,
    passed: false,
    message_key: "rules.MIN_AVAILABILITY_COUNT",
    message_params: { required: 1, actual: 0 },
  },
];

function renderCalendar(validation = FAILING_VALIDATION) {
  return render(
    <AvailabilityCalendar
      periodId="period-1"
      userId="user-1"
      editable
      readOnlyMessageKey={null}
      reopenedNotice={false}
      slots={[SLOT]}
      shiftTypes={[MORNING]}
      initialEntries={[]}
      initialValidation={validation}
      initialSubmissionStatus="DRAFT"
      previousSlots={null}
      previousStatusBySlotId={null}
    />,
  );
}

describe("AvailabilityCalendar", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
    vi.mocked(api.writeAvailability).mockResolvedValue(detailWith(PASSING_VALIDATION));
    vi.mocked(api.submitAvailability).mockResolvedValue(detailWith(PASSING_VALIDATION));
  });

  it("cycles a chip unavailable -> available -> preferred -> unavailable on tap", async () => {
    renderCalendar();
    const user = userEvent.setup();
    const chip = screen.getByRole("button", { name: /morning — unavailable/i });

    await user.click(chip);
    expect(screen.getByRole("button", { name: /morning — available/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /morning — available/i }));
    expect(screen.getByRole("button", { name: /morning — preferred/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /morning — preferred/i }));
    expect(screen.getByRole("button", { name: /morning — unavailable/i })).toBeInTheDocument();
  });

  it("shows the requirements bar and reflects the latest validation after a save", async () => {
    renderCalendar(FAILING_VALIDATION);
    expect(screen.getByText("0/1 shifts declared")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /morning — unavailable/i }));

    await waitFor(() => expect(api.writeAvailability).toHaveBeenCalled(), { timeout: 2000 });
    await waitFor(() => expect(screen.getByText("1/1 shifts declared")).toBeInTheDocument());
  });

  it("disables submit while a HARD rule fails, and enables it once all pass", async () => {
    renderCalendar(FAILING_VALIDATION);
    expect(screen.getByRole("button", { name: /submit availability/i })).toBeDisabled();
    expect(screen.getByText(/complete the requirements above/i)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /morning — unavailable/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit availability/i })).toBeEnabled(),
    );
  });

  it("clear all bulk action resets every slot to unavailable", async () => {
    window.confirm = vi.fn(() => true);
    renderCalendar(PASSING_VALIDATION);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /morning — unavailable/i }));
    expect(screen.getByRole("button", { name: /morning — available/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /clear all/i }));

    expect(screen.getByRole("button", { name: /morning — unavailable/i })).toBeInTheDocument();
  });
});

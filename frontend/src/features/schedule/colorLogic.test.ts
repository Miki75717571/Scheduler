import { describe, expect, it } from "vitest";

import type { ScheduleViolation } from "../../api/types";
import { computeSlotStatus, violationsForSlot } from "./colorLogic";

const SLOT = { is_closed: false, min_staff: 1, required_staff: 2 };

function violation(overrides: Partial<ScheduleViolation> = {}): ScheduleViolation {
  return {
    severity: "ERROR",
    rule_code: "UNDERSTAFFING",
    rule_type: "UNDERSTAFFING",
    message_key: "schedule.understaffed_below_minimum",
    message_params: {},
    shift_slot_id: "slot-1",
    user_id: null,
    ...overrides,
  };
}

describe("computeSlotStatus", () => {
  it("is closed for a closed slot regardless of staffing", () => {
    expect(computeSlotStatus({ ...SLOT, is_closed: true }, 0, [])).toBe("closed");
  });

  it("is red when below min_staff even with no violations recorded", () => {
    expect(computeSlotStatus(SLOT, 0, [])).toBe("red");
  });

  it("is red when any ERROR violation touches the slot, even if fully staffed", () => {
    expect(computeSlotStatus(SLOT, 2, [violation({ severity: "ERROR" })])).toBe("red");
  });

  it("is amber when at or above min_staff but below required_staff", () => {
    expect(computeSlotStatus(SLOT, 1, [])).toBe("amber");
  });

  it("is amber when a WARNING violation touches the slot, even if fully staffed", () => {
    expect(computeSlotStatus(SLOT, 2, [violation({ severity: "WARNING" })])).toBe("amber");
  });

  it("is green when fully staffed and legal", () => {
    expect(computeSlotStatus(SLOT, 2, [])).toBe("green");
  });

  it("ERROR outranks WARNING when both are present", () => {
    const violations = [violation({ severity: "WARNING" }), violation({ severity: "ERROR" })];
    expect(computeSlotStatus(SLOT, 2, violations)).toBe("red");
  });
});

describe("violationsForSlot", () => {
  it("matches a violation with a direct shift_slot_id", () => {
    const v = violation({ shift_slot_id: "slot-1" });
    expect(violationsForSlot("slot-1", [v])).toEqual([v]);
    expect(violationsForSlot("slot-2", [v])).toEqual([]);
  });

  it("matches a slotless violation via message_params.shift_slot_ids", () => {
    const v = violation({
      shift_slot_id: null,
      message_key: "rules.ONE_SHIFT_PER_DAY",
      message_params: { shift_slot_ids: ["slot-9", "slot-1"] },
    });
    expect(violationsForSlot("slot-1", [v])).toEqual([v]);
    expect(violationsForSlot("slot-5", [v])).toEqual([]);
  });

  it("matches a MIN_REST_HOURS violation via from/to shift ids", () => {
    const v = violation({
      shift_slot_id: "slot-2",
      message_key: "rules.MIN_REST_HOURS",
      message_params: { from_shift_slot_id: "slot-1", to_shift_slot_id: "slot-2" },
    });
    expect(violationsForSlot("slot-1", [v])).toEqual([v]);
    expect(violationsForSlot("slot-2", [v])).toEqual([v]);
    expect(violationsForSlot("slot-3", [v])).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";

import type { ShiftSlot, ShiftType } from "../../api/types";
import {
  allMorningsPatch,
  allWeekdayEveningsPatch,
  allWeekendsPatch,
  clearAllPatch,
  copyFromLastMonthPatch,
} from "./bulkActions";

function shiftType(overrides: Partial<ShiftType>): ShiftType {
  return {
    id: "st-default",
    code: "CODE",
    name_pl: "Nazwa",
    name_en: "Name",
    start_time: "09:00:00",
    end_time: "17:00:00",
    color_hex: "#000000",
    active_weekdays: 127,
    default_required_staff: 1,
    default_min_staff: 1,
    default_max_staff: 2,
    sort_order: 0,
    is_active: true,
    ...overrides,
  };
}

function slot(overrides: Partial<ShiftSlot>): ShiftSlot {
  return {
    id: "slot-default",
    period_id: "period-1",
    date: "2027-03-01",
    shift_type_id: "st-default",
    required_staff: 1,
    min_staff: 1,
    max_staff: 2,
    is_closed: false,
    note: null,
    start_time: "09:00:00",
    end_time: "17:00:00",
    ...overrides,
  };
}

const MORNING = shiftType({
  id: "morning",
  code: "MORNING",
  start_time: "07:00:00",
  sort_order: 0,
});
const EVENING = shiftType({
  id: "evening",
  code: "EVENING",
  start_time: "15:00:00",
  sort_order: 1,
});
const shiftTypesById = { morning: MORNING, evening: EVENING };

// 2027-03-01 is a Monday, 2027-03-06/07 are Sat/Sun.
const MON = "2027-03-01";
const SAT = "2027-03-06";
const SUN = "2027-03-07";

describe("allMorningsPatch", () => {
  it("marks only the earliest-starting open shift each day, regardless of shift code", () => {
    const slots = [
      slot({ id: "mon-morning", date: MON, shift_type_id: "morning" }),
      slot({ id: "mon-evening", date: MON, shift_type_id: "evening" }),
    ];
    expect(allMorningsPatch(slots, shiftTypesById)).toEqual({ "mon-morning": "AVAILABLE" });
  });

  it("skips closed shifts", () => {
    const slots = [
      slot({ id: "mon-morning", date: MON, shift_type_id: "morning", is_closed: true }),
      slot({ id: "mon-evening", date: MON, shift_type_id: "evening" }),
    ];
    expect(allMorningsPatch(slots, shiftTypesById)).toEqual({ "mon-evening": "AVAILABLE" });
  });
});

describe("allWeekdayEveningsPatch", () => {
  it("marks the latest-starting shift on weekdays only", () => {
    const slots = [
      slot({ id: "mon-morning", date: MON, shift_type_id: "morning" }),
      slot({ id: "mon-evening", date: MON, shift_type_id: "evening" }),
      slot({ id: "sat-morning", date: SAT, shift_type_id: "morning" }),
      slot({ id: "sat-evening", date: SAT, shift_type_id: "evening" }),
    ];
    expect(allWeekdayEveningsPatch(slots, shiftTypesById)).toEqual({ "mon-evening": "AVAILABLE" });
  });
});

describe("allWeekendsPatch", () => {
  it("marks every open shift on Saturday and Sunday, ignoring weekdays", () => {
    const slots = [
      slot({ id: "mon-morning", date: MON, shift_type_id: "morning" }),
      slot({ id: "sat-morning", date: SAT, shift_type_id: "morning" }),
      slot({ id: "sat-evening", date: SAT, shift_type_id: "evening" }),
      slot({ id: "sun-morning", date: SUN, shift_type_id: "morning", is_closed: true }),
    ];
    expect(allWeekendsPatch(slots)).toEqual({
      "sat-morning": "AVAILABLE",
      "sat-evening": "AVAILABLE",
    });
  });
});

describe("clearAllPatch", () => {
  it("sets every slot to UNAVAILABLE", () => {
    const slots = [slot({ id: "a" }), slot({ id: "b" })];
    expect(clearAllPatch(slots)).toEqual({ a: "UNAVAILABLE", b: "UNAVAILABLE" });
  });
});

describe("copyFromLastMonthPatch", () => {
  it("carries over the weekday+shift-type pattern from last month, keyed by shift_type_id", () => {
    const previousSlots = [
      slot({ id: "prev-mon-morning", date: "2027-02-01", shift_type_id: "morning" }), // Monday
      slot({ id: "prev-mon-evening", date: "2027-02-01", shift_type_id: "evening" }),
    ];
    const previousStatus = {
      "prev-mon-morning": "PREFERRED",
      "prev-mon-evening": "AVAILABLE",
    } as const;
    const currentSlots = [
      slot({ id: "cur-mon-morning", date: MON, shift_type_id: "morning" }),
      slot({ id: "cur-mon-evening", date: MON, shift_type_id: "evening" }),
    ];

    expect(copyFromLastMonthPatch(currentSlots, previousSlots, previousStatus)).toEqual({
      "cur-mon-morning": "PREFERRED",
      "cur-mon-evening": "AVAILABLE",
    });
  });

  it("skips closed slots and slots with no matching history", () => {
    const previousSlots = [slot({ id: "prev", date: "2027-02-01", shift_type_id: "morning" })];
    const previousStatus = { prev: "AVAILABLE" } as const;
    const currentSlots = [
      slot({ id: "closed", date: MON, shift_type_id: "morning", is_closed: true }),
      slot({ id: "no-history", date: MON, shift_type_id: "evening" }),
    ];

    expect(copyFromLastMonthPatch(currentSlots, previousSlots, previousStatus)).toEqual({});
  });
});

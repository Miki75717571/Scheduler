import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ShiftSlot, ShiftType } from "../../api/types";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

interface SlotDraft {
  required_staff: number;
  min_staff: number;
  max_staff: number;
  is_closed: boolean;
  note: string;
}

interface SlotOverridesTableProps {
  slots: ShiftSlot[];
  shiftTypesById: Record<string, ShiftType>;
  onSave: (
    slotId: string,
    payload: Pick<ShiftSlot, "required_staff" | "min_staff" | "max_staff" | "is_closed" | "note">,
  ) => Promise<void>;
}

function toDraft(slot: ShiftSlot): SlotDraft {
  return {
    required_staff: slot.required_staff,
    min_staff: slot.min_staff,
    max_staff: slot.max_staff,
    is_closed: slot.is_closed,
    note: slot.note ?? "",
  };
}

export function SlotOverridesTable({ slots, shiftTypesById, onSave }: SlotOverridesTableProps) {
  const { t, i18n } = useTranslation();
  const [drafts, setDrafts] = useState<Record<string, SlotDraft>>(() =>
    Object.fromEntries(slots.map((s) => [s.id, toDraft(s)])),
  );
  const [rowStatus, setRowStatus] = useState<Record<string, "idle" | "saving" | "saved" | "error">>(
    {},
  );

  function updateDraft(slotId: string, patch: Partial<SlotDraft>) {
    setDrafts((prev) => ({ ...prev, [slotId]: { ...prev[slotId], ...patch } }));
    setRowStatus((prev) => ({ ...prev, [slotId]: "idle" }));
  }

  async function handleSave(slotId: string) {
    const draft = drafts[slotId];
    setRowStatus((prev) => ({ ...prev, [slotId]: "saving" }));
    try {
      await onSave(slotId, {
        required_staff: draft.required_staff,
        min_staff: draft.min_staff,
        max_staff: draft.max_staff,
        is_closed: draft.is_closed,
        note: draft.note || null,
      });
      setRowStatus((prev) => ({ ...prev, [slotId]: "saved" }));
    } catch {
      setRowStatus((prev) => ({ ...prev, [slotId]: "error" }));
    }
  }

  const sortedSlots = [...slots].sort(
    (a, b) =>
      a.date.localeCompare(b.date) ||
      shiftTypesById[a.shift_type_id].sort_order - shiftTypesById[b.shift_type_id].sort_order,
  );

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-secondary text-secondary-foreground">
          <tr>
            <th className="px-2 py-2">{t("manager.slotDate")}</th>
            <th className="px-2 py-2">{t("manager.slotShift")}</th>
            <th className="px-2 py-2">{t("manager.slotMin")}</th>
            <th className="px-2 py-2">{t("manager.slotRequired")}</th>
            <th className="px-2 py-2">{t("manager.slotMax")}</th>
            <th className="px-2 py-2">{t("manager.slotClosed")}</th>
            <th className="px-2 py-2">{t("manager.slotNote")}</th>
            <th className="px-2 py-2" />
          </tr>
        </thead>
        <tbody>
          {sortedSlots.map((slot) => {
            const draft = drafts[slot.id];
            const shiftType = shiftTypesById[slot.shift_type_id];
            const invalid = !(draft.min_staff <= draft.required_staff && draft.required_staff <= draft.max_staff);
            const status = rowStatus[slot.id] ?? "idle";
            return (
              <tr key={slot.id} className="border-t border-border align-top">
                <td className="whitespace-nowrap px-2 py-2">{slot.date}</td>
                <td className="whitespace-nowrap px-2 py-2">
                  {i18n.language === "pl" ? shiftType.name_pl : shiftType.name_en}
                </td>
                <td className="px-2 py-2">
                  <Input
                    type="number"
                    min={0}
                    className="h-8 w-16"
                    value={draft.min_staff}
                    onChange={(e) => updateDraft(slot.id, { min_staff: Number(e.target.value) })}
                  />
                </td>
                <td className="px-2 py-2">
                  <Input
                    type="number"
                    min={0}
                    className="h-8 w-16"
                    value={draft.required_staff}
                    onChange={(e) => updateDraft(slot.id, { required_staff: Number(e.target.value) })}
                  />
                </td>
                <td className="px-2 py-2">
                  <Input
                    type="number"
                    min={0}
                    className="h-8 w-16"
                    value={draft.max_staff}
                    onChange={(e) => updateDraft(slot.id, { max_staff: Number(e.target.value) })}
                  />
                </td>
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    aria-label={t("manager.slotClosed")}
                    checked={draft.is_closed}
                    onChange={(e) => updateDraft(slot.id, { is_closed: e.target.checked })}
                  />
                </td>
                <td className="px-2 py-2">
                  <Input
                    className="h-8 w-32"
                    value={draft.note}
                    onChange={(e) => updateDraft(slot.id, { note: e.target.value })}
                  />
                </td>
                <td className="whitespace-nowrap px-2 py-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={invalid || status === "saving"}
                    onClick={() => void handleSave(slot.id)}
                  >
                    {t("common.save")}
                  </Button>
                  {invalid && (
                    <p className="mt-1 text-xs text-destructive">
                      {t("apiErrors.shift_slot.invalid_staff_levels")}
                    </p>
                  )}
                  {status === "saved" && (
                    <p className="mt-1 text-xs text-emerald-700">{t("availability.saveStatusSaved")}</p>
                  )}
                  {status === "error" && (
                    <p className="mt-1 text-xs text-destructive">
                      {t("availability.saveStatusErrorFinal")}
                    </p>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

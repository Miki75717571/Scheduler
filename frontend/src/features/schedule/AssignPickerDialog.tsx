import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { AvailableEmployee } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { cn } from "../../lib/utils";

interface RosterMember {
  user_id: string;
  full_name: string;
}

interface AssignPickerDialogProps {
  shiftTypeName: string;
  dateLabel: string;
  roster: RosterMember[];
  assignedUserIds: Set<string>;
  candidates: AvailableEmployee[];
  loading: boolean;
  error: unknown;
  pendingUserId: string | null;
  onPick: (userId: string) => void;
  onClose: () => void;
}

function byName(a: { full_name: string }, b: { full_name: string }): number {
  return a.full_name.localeCompare(b.full_name);
}

// THE core interaction (see CLAUDE.md/the task brief): this is what replaces
// the manager's spreadsheet, so candidates are ranked exactly as asked -
// PREFERRED first, then AVAILABLE, both sorted by name - with everyone else
// (declared UNAVAILABLE, hard-rule-excluded, or never submitted at all -
// backend/app/services/schedule_service.py's available_employees() collapses
// all three into "not a clean candidate") reachable but tucked away behind an
// explicit warning, never silently hidden.
export function AssignPickerDialog({
  shiftTypeName,
  dateLabel,
  roster,
  assignedUserIds,
  candidates,
  loading,
  error,
  pendingUserId,
  onPick,
  onClose,
}: AssignPickerDialogProps) {
  const { t } = useTranslation();
  const [showUnavailable, setShowUnavailable] = useState(false);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const { preferred, available, unavailable } = useMemo(() => {
    const preferred = candidates
      .filter((c) => c.status === "PREFERRED" && !assignedUserIds.has(c.user_id))
      .sort(byName);
    const available = candidates
      .filter((c) => c.status === "AVAILABLE" && !assignedUserIds.has(c.user_id))
      .sort(byName);
    const clearIds = new Set([...preferred, ...available].map((c) => c.user_id));
    const unavailable = roster
      .filter((u) => !assignedUserIds.has(u.user_id) && !clearIds.has(u.user_id))
      .sort(byName);
    return { preferred, available, unavailable };
  }, [candidates, roster, assignedUserIds]);

  const nobodyAtAll = !loading && preferred.length === 0 && available.length === 0 && unavailable.length === 0;

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4 print:hidden"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-picker-title"
        onClick={(event) => event.stopPropagation()}
        className="max-h-[80vh] w-full max-w-sm overflow-y-auto rounded-lg bg-background p-4 shadow-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 id="assign-picker-title" className="text-sm font-semibold">
            {t("schedule.pickerTitle", { shift: shiftTypeName, date: dateLabel })}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("schedule.pickerClose")}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>

        {loading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
        {error !== null && error !== undefined && <ApiErrorText error={error} />}

        {!loading && (
          <div className="space-y-3">
            {preferred.length > 0 && (
              <CandidateGroup
                heading={t("schedule.pickerPreferred")}
                icon="★"
                members={preferred}
                pendingUserId={pendingUserId}
                onPick={onPick}
              />
            )}
            {available.length > 0 && (
              <CandidateGroup
                heading={t("schedule.pickerAvailable")}
                icon="✓"
                members={available}
                pendingUserId={pendingUserId}
                onPick={onPick}
              />
            )}
            {nobodyAtAll && (
              <p className="text-sm text-muted-foreground">{t("schedule.pickerNoCandidates")}</p>
            )}

            {unavailable.length > 0 && (
              <div className="border-t border-border pt-2">
                <button
                  type="button"
                  onClick={() => setShowUnavailable((v) => !v)}
                  className="text-xs font-medium text-muted-foreground hover:text-foreground"
                >
                  {showUnavailable ? "▾ " : "▸ "}
                  {t("schedule.pickerUnavailableSection", { count: unavailable.length })}
                </button>
                {showUnavailable && (
                  <div className="mt-2 space-y-2">
                    <p className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-900">
                      {t("schedule.pickerUnavailableWarning")}
                    </p>
                    <CandidateGroup
                      heading=""
                      icon="⚠"
                      members={unavailable}
                      pendingUserId={pendingUserId}
                      onPick={onPick}
                      warn
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CandidateGroup({
  heading,
  icon,
  members,
  pendingUserId,
  onPick,
  warn = false,
}: {
  heading: string;
  icon: string;
  members: { user_id: string; full_name: string }[];
  pendingUserId: string | null;
  onPick: (userId: string) => void;
  warn?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1">
      {heading && <h3 className="text-xs font-semibold text-muted-foreground">{heading}</h3>}
      <ul className="space-y-1">
        {members.map((member) => (
          <li key={member.user_id}>
            <button
              type="button"
              disabled={pendingUserId !== null}
              onClick={() => onPick(member.user_id)}
              className={cn(
                "flex w-full items-center gap-2 rounded border px-2 py-1.5 text-left text-sm hover:bg-secondary disabled:opacity-50",
                warn ? "border-amber-300 text-amber-900" : "border-border",
              )}
            >
              <span aria-hidden="true">{icon}</span>
              <span className="flex-1">{member.full_name}</span>
              {pendingUserId === member.user_id && (
                <span className="text-xs text-muted-foreground">{t("schedule.pickerAssigning")}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

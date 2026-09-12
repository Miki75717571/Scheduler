import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { SubmissionTrackerEntry } from "../../api/types";
import { Button } from "../../components/ui/button";

type SortKey = "full_name" | "status" | "submitted_at";

interface SubmissionTrackerProps {
  entries: SubmissionTrackerEntry[];
  periodLocked: boolean;
  onReopen: (userId: string) => void;
  onRevokeReopen: (userId: string) => void;
  pendingUserId: string | null;
}

const STATUS_ORDER: Record<string, number> = { NOT_STARTED: 0, DRAFT: 1, SUBMITTED: 2 };
const STATUS_COLOR: Record<string, string> = {
  NOT_STARTED: "text-muted-foreground",
  DRAFT: "text-amber-700",
  SUBMITTED: "text-emerald-700",
};

export function SubmissionTracker({
  entries,
  periodLocked,
  onReopen,
  onRevokeReopen,
  pendingUserId,
}: SubmissionTrackerProps) {
  const { t } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>("full_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const counts = useMemo(
    () => ({
      submitted: entries.filter((e) => e.status === "SUBMITTED").length,
      draft: entries.filter((e) => e.status === "DRAFT").length,
      notStarted: entries.filter((e) => e.status === "NOT_STARTED").length,
    }),
    [entries],
  );

  const sorted = useMemo(() => {
    const copy = [...entries];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "full_name") cmp = a.full_name.localeCompare(b.full_name);
      else if (sortKey === "status") cmp = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
      else cmp = (a.submitted_at ?? "").localeCompare(b.submitted_at ?? "");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [entries, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {t("manager.trackerCounts", {
          submitted: counts.submitted,
          draft: counts.draft,
          notStarted: counts.notStarted,
        })}
      </p>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead className="bg-secondary text-secondary-foreground">
            <tr>
              <th className="cursor-pointer select-none px-3 py-2" onClick={() => toggleSort("full_name")}>
                {t("manager.columnName")}
              </th>
              <th className="cursor-pointer select-none px-3 py-2" onClick={() => toggleSort("status")}>
                {t("manager.columnStatus")}
              </th>
              <th
                className="cursor-pointer select-none px-3 py-2"
                onClick={() => toggleSort("submitted_at")}
              >
                {t("manager.columnSubmittedAt")}
              </th>
              {periodLocked && <th className="px-3 py-2">{t("manager.columnActions")}</th>}
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry) => (
              <tr key={entry.user_id} className="border-t border-border">
                <td className="px-3 py-2">{entry.full_name}</td>
                <td className="px-3 py-2">
                  <span className={STATUS_COLOR[entry.status]}>
                    {t(`availability.submissionStatus.${entry.status}`)}
                  </span>
                  {entry.reopened_by_manager && (
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({t("manager.reopenedBadge")})
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {entry.submitted_at ? new Date(entry.submitted_at).toLocaleString() : "—"}
                </td>
                {periodLocked && (
                  <td className="px-3 py-2">
                    {entry.reopened_by_manager ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={pendingUserId === entry.user_id}
                        onClick={() => onRevokeReopen(entry.user_id)}
                      >
                        {t("manager.revokeReopenButton")}
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={pendingUserId === entry.user_id}
                        onClick={() => onReopen(entry.user_id)}
                      >
                        {t("manager.reopenButton")}
                      </Button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

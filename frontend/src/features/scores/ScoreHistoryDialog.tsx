import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import type { ScoreHistoryEntry } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";

interface ScoreHistoryDialogProps {
  employeeName: string;
  entries: ScoreHistoryEntry[] | undefined;
  loading: boolean;
  error: unknown;
  onClose: () => void;
}

export function ScoreHistoryDialog({
  employeeName,
  entries,
  loading,
  error,
  onClose,
}: ScoreHistoryDialogProps) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-history-title"
        onClick={(event) => event.stopPropagation()}
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-background p-4 shadow-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 id="score-history-title" className="text-sm font-semibold">
            {t("scores.historyTitle", { name: employeeName })}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("scores.historyClose")}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>

        {loading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
        {error !== null && error !== undefined && <ApiErrorText error={error} />}

        {!loading && entries !== undefined && entries.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("scores.historyEmpty")}</p>
        )}

        {!loading && entries !== undefined && entries.length > 0 && (
          <ul className="space-y-3">
            {entries.map((entry) => (
              <li key={entry.id} className="rounded border border-border p-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {i18n.language === "pl" ? entry.criterion_name_pl : entry.criterion_name_en}
                  </span>
                  <span>
                    {entry.previous_value === null
                      ? t("scores.historyFirstRating", { value: entry.value })
                      : t("scores.historyChange", {
                          previous: entry.previous_value,
                          value: entry.value,
                        })}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("scores.historySetBy", {
                    name: entry.set_by_full_name,
                    date: new Date(entry.created_at).toLocaleString(
                      i18n.language === "pl" ? "pl-PL" : "en-US",
                    ),
                  })}
                </p>
                {entry.note && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("scores.historyNote", { note: entry.note })}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

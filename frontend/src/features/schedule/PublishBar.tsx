import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PeriodState } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { Button } from "../../components/ui/button";

interface PublishBarProps {
  periodState: PeriodState;
  publishedAt: string | null;
  totalSlots: number;
  totalAssignments: number;
  errorCount: number;
  modifiedAfterPublishCount: number;
  onPublish: (overrideViolations: boolean) => Promise<void>;
}

export function PublishBar({
  periodState,
  publishedAt,
  totalSlots,
  totalAssignments,
  errorCount,
  modifiedAfterPublishCount,
  onPublish,
}: PublishBarProps) {
  const { t, i18n } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (periodState === "PUBLISHED") {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3 text-sm print:hidden">
        <span className="font-medium text-emerald-700">
          {t("schedule.publishedBadge", {
            date: publishedAt
              ? new Date(publishedAt).toLocaleDateString(i18n.language === "pl" ? "pl-PL" : "en-US")
              : "",
          })}
        </span>
        {modifiedAfterPublishCount > 0 && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-900">
            {t("schedule.publishedChangedWarning", { count: modifiedAfterPublishCount })}
          </span>
        )}
      </div>
    );
  }

  if (periodState !== "GENERATED") {
    return <p className="text-sm text-muted-foreground print:hidden">{t("schedule.generatedHint")}</p>;
  }

  async function handleConfirm() {
    setPending(true);
    setError(null);
    try {
      await onPublish(errorCount > 0);
      setConfirming(false);
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-border p-3 print:hidden">
      <p className="text-sm text-muted-foreground">
        {t("schedule.publishSummaryAssigned", { assigned: totalAssignments, slots: totalSlots })}
      </p>
      {errorCount > 0 && (
        <p className="text-sm text-red-700">{t("schedule.publishErrorsWarning", { count: errorCount })}</p>
      )}
      {!confirming ? (
        <Button type="button" onClick={() => setConfirming(true)}>
          {t("schedule.publishButton")}
        </Button>
      ) : (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-300 bg-amber-50 p-2">
          <span className="text-sm text-amber-900">
            {errorCount > 0
              ? t("schedule.publishOverrideConfirm", { count: errorCount })
              : t("schedule.publishConfirm")}
          </span>
          <Button type="button" size="sm" disabled={pending} onClick={() => void handleConfirm()}>
            {t("common.confirm")}
          </Button>
          <Button type="button" size="sm" variant="secondary" onClick={() => setConfirming(false)}>
            {t("common.cancel")}
          </Button>
        </div>
      )}
      {error !== null && <ApiErrorText error={error} />}
    </div>
  );
}

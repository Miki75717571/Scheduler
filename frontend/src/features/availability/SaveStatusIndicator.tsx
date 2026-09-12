import { useTranslation } from "react-i18next";

import type { SaveStatus } from "../../hooks/useAutosave";

interface SaveStatusIndicatorProps {
  status: SaveStatus;
  onRetry: () => void;
}

export function SaveStatusIndicator({ status, onRetry }: SaveStatusIndicatorProps) {
  const { t } = useTranslation();

  if (status === "idle") return null;

  if (status === "saving") {
    return (
      <span className="text-xs text-muted-foreground">{t("availability.saveStatusSaving")}</span>
    );
  }

  if (status === "error") {
    return (
      <span className="flex items-center gap-2 text-xs text-destructive">
        {t("availability.saveStatusError")}
        <button type="button" onClick={onRetry} className="underline underline-offset-2">
          {t("availability.retryNow")}
        </button>
      </span>
    );
  }

  return <span className="text-xs text-emerald-700">{t("availability.saveStatusSaved")}</span>;
}

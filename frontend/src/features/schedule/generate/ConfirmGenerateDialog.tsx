import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { ApiErrorText } from "../../../components/ApiErrorText";
import { Button } from "../../../components/ui/button";

interface ConfirmGenerateDialogProps {
  lockedCount: number;
  discardCount: number;
  pending: boolean;
  error: unknown;
  onConfirm: () => void;
  onCancel: () => void;
}

// The one screen standing between the manager and losing an hour of manual
// edits (the task brief's "unforgivable" scenario): every regenerate must
// show exactly what survives (locked) and what gets thrown away (everything
// else) before it happens, never after.
export function ConfirmGenerateDialog({
  lockedCount,
  discardCount,
  pending,
  error,
  onConfirm,
  onCancel,
}: ConfirmGenerateDialogProps) {
  const { t } = useTranslation();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4 print:hidden"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-generate-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-sm space-y-3 rounded-lg bg-background p-4 shadow-xl"
      >
        <h2 id="confirm-generate-title" className="text-sm font-semibold">
          {t("generate.confirmTitle")}
        </h2>

        <div className="space-y-1 text-sm">
          {lockedCount === 0 && discardCount === 0 ? (
            <p className="text-muted-foreground">{t("generate.confirmNoExisting")}</p>
          ) : (
            <>
              {lockedCount > 0 && (
                <p className="rounded border border-slate-300 bg-slate-50 px-2 py-1">
                  🔒 {t("generate.confirmLockedCount", { count: lockedCount })}
                </p>
              )}
              {discardCount > 0 && (
                <p className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-amber-900">
                  {t("generate.confirmDiscardCount", { count: discardCount })}
                </p>
              )}
            </>
          )}
        </div>

        {error !== null && <ApiErrorText error={error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={pending}>
            {t("common.cancel")}
          </Button>
          <Button type="button" onClick={onConfirm} disabled={pending}>
            {t("generate.confirmButton")}
          </Button>
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PeriodState } from "../../api/types";
import { ApiErrorText } from "../../components/ApiErrorText";
import { Button } from "../../components/ui/button";

const NEXT_STATE: Partial<Record<PeriodState, PeriodState>> = {
  DRAFT: "COLLECTING",
  COLLECTING: "LOCKED",
  LOCKED: "GENERATED",
  GENERATED: "PUBLISHED",
};

const TRANSITION_LABEL_KEY: Partial<Record<PeriodState, string>> = {
  COLLECTING: "manager.transition.openCollecting",
  LOCKED: "manager.transition.lock",
  GENERATED: "manager.transition.generate",
  PUBLISHED: "manager.transition.publish",
};

interface PeriodStateControlsProps {
  state: PeriodState;
  onTransition: (target: PeriodState) => Promise<void>;
}

// Every forward transition here is permanent - app/services/period_service.py
// only ever allows moving forward, never back - so each one gets an inline
// confirm step rather than firing straight away.
export function PeriodStateControls({ state, onTransition }: PeriodStateControlsProps) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const target = NEXT_STATE[state];
  if (!target) {
    return <p className="text-sm text-muted-foreground">{t("manager.periodFinal")}</p>;
  }

  const label = t(TRANSITION_LABEL_KEY[target] ?? "");

  if (!confirming) {
    return (
      <div className="space-y-1">
        <Button type="button" onClick={() => setConfirming(true)}>
          {label}
        </Button>
        {error !== null && <ApiErrorText error={error} />}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-300 bg-amber-50 p-3">
      <span className="text-sm text-amber-900">{t("manager.confirmTransition", { action: label })}</span>
      <Button
        type="button"
        size="sm"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await onTransition(target);
            setConfirming(false);
          } catch (err) {
            setError(err);
          } finally {
            setPending(false);
          }
        }}
      >
        {t("common.confirm")}
      </Button>
      <Button type="button" size="sm" variant="secondary" onClick={() => setConfirming(false)}>
        {t("common.cancel")}
      </Button>
    </div>
  );
}

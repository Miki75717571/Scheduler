import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Assignment, PeriodState } from "../../../api/types";
import { ApiErrorText } from "../../../components/ApiErrorText";
import { Button } from "../../../components/ui/button";
import { createScheduleRun, fetchScheduleRun, fetchScheduleRuns, revertScheduleRun } from "./api";
import { ConfirmGenerateDialog } from "./ConfirmGenerateDialog";
import { RunDiagnostics } from "./RunDiagnostics";
import { RunHistory } from "./RunHistory";
import { RunStats } from "./RunStats";

const POLL_INTERVAL_MS = 1500;
// Backend default time limit is 30s (ARCHITECTURE.md ss2); anything still
// running well past that plus polling/roundtrip slack is worth telling the
// manager about explicitly rather than leaving a spinner that never stops
// (task brief: "handle a failed or timed-out run with a readable message").
const CLIENT_TIMEOUT_MS = 90_000;

const RUNNABLE_STATES: PeriodState[] = ["LOCKED", "GENERATED"];

interface GeneratePanelProps {
  periodId: string;
  periodState: PeriodState;
  assignments: Assignment[];
  nameById: Record<string, string>;
  shiftTypeNameByCode: Record<string, string>;
  onJumpToDate?: (date: string) => void;
}

export function GeneratePanel({
  periodId,
  periodState,
  assignments,
  nameById,
  shiftTypeNameByCode,
  onJumpToDate,
}: GeneratePanelProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [confirming, setConfirming] = useState(false);
  const [createPending, setCreatePending] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [revertPendingId, setRevertPendingId] = useState<string | null>(null);
  const [revertError, setRevertError] = useState<unknown>(null);
  const handledRunIdRef = useRef<string | null>(null);

  const historyQuery = useQuery({
    queryKey: ["schedule-runs", periodId],
    queryFn: () => fetchScheduleRuns(periodId),
  });

  const activeRunQuery = useQuery({
    queryKey: ["schedule-run", activeRunId],
    queryFn: () => fetchScheduleRun(activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "SUCCESS" || status === "FAILED" ? false : POLL_INTERVAL_MS;
    },
  });

  useEffect(() => {
    const run = activeRunQuery.data;
    if (!run || run.id === handledRunIdRef.current) return;
    if (run.status === "SUCCESS" || run.status === "FAILED") {
      handledRunIdRef.current = run.id;
      setSelectedRunId(run.id);
      void queryClient.invalidateQueries({ queryKey: ["schedule-runs", periodId] });
      if (run.status === "SUCCESS") {
        void queryClient.invalidateQueries({ queryKey: ["assignments", periodId] });
        void queryClient.invalidateQueries({ queryKey: ["violations", periodId] });
      }
    }
  }, [activeRunQuery.data, periodId, queryClient]);

  const runs = historyQuery.data ?? [];
  const selectedRun =
    runs.find((r) => r.id === selectedRunId) ??
    (activeRunQuery.data?.id === selectedRunId ? activeRunQuery.data : null);

  const canGenerate = RUNNABLE_STATES.includes(periodState);
  const disabledReasonKey =
    periodState === "PUBLISHED" ? "generate.disabledPublished" : "generate.disabledNotLocked";
  const isRunning =
    activeRunQuery.data !== undefined &&
    (activeRunQuery.data.status === "PENDING" || activeRunQuery.data.status === "RUNNING");
  const timedOut = Boolean(
    isRunning && runStartedAt !== null && Date.now() - runStartedAt > CLIENT_TIMEOUT_MS,
  );

  const lockedCount = assignments.filter((a) => a.is_locked).length;
  const discardCount = assignments.length - lockedCount;

  async function handleConfirm() {
    setCreatePending(true);
    setCreateError(null);
    try {
      const run = await createScheduleRun(periodId);
      handledRunIdRef.current = null;
      setActiveRunId(run.id);
      setSelectedRunId(run.id);
      setRunStartedAt(Date.now());
      setConfirming(false);
    } catch (error) {
      setCreateError(error);
    } finally {
      setCreatePending(false);
    }
  }

  async function handleRevert(runId: string) {
    setRevertPendingId(runId);
    setRevertError(null);
    try {
      await revertScheduleRun(runId);
      await queryClient.invalidateQueries({ queryKey: ["schedule-runs", periodId] });
      await queryClient.invalidateQueries({ queryKey: ["assignments", periodId] });
      await queryClient.invalidateQueries({ queryKey: ["violations", periodId] });
    } catch (error) {
      setRevertError(error);
    } finally {
      setRevertPendingId(null);
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-3 print:hidden">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          {runs.length > 0 ? t("generate.regenerateButton") : t("generate.button")}
        </h2>
        {canGenerate ? (
          <Button type="button" disabled={isRunning} onClick={() => setConfirming(true)}>
            {runs.length > 0 ? t("generate.regenerateButton") : t("generate.button")}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">{t(disabledReasonKey)}</p>
        )}
      </div>

      {activeRunQuery.data && (
        <div className="rounded-md border px-2 py-1.5 text-sm" role="status" aria-live="polite">
          {activeRunQuery.data.status === "PENDING" && <p>{t("generate.statusPending")}</p>}
          {activeRunQuery.data.status === "RUNNING" && (
            <p>
              {t("generate.statusRunning", {
                seconds: activeRunQuery.data.params_snapshot.time_limit_seconds,
              })}
            </p>
          )}
          {activeRunQuery.data.status === "SUCCESS" && (
            <p className="text-emerald-700">{t("generate.statusSuccess")}</p>
          )}
          {activeRunQuery.data.status === "FAILED" && (
            <p className="text-red-700">
              {t("generate.statusFailed", {
                message: activeRunQuery.data.error_message ?? t("error.unknown"),
              })}
            </p>
          )}
          {timedOut && <p className="mt-1 text-amber-700">{t("generate.statusTimeout")}</p>}
        </div>
      )}
      {activeRunQuery.error !== null && activeRunQuery.error !== undefined && (
        <ApiErrorText error={activeRunQuery.error} />
      )}

      {confirming && (
        <ConfirmGenerateDialog
          lockedCount={lockedCount}
          discardCount={discardCount}
          pending={createPending}
          error={createError}
          onConfirm={() => void handleConfirm()}
          onCancel={() => {
            setConfirming(false);
            setCreateError(null);
          }}
        />
      )}

      {selectedRun?.status === "SUCCESS" && (
        <div className="space-y-3">
          <RunStats run={selectedRun} nameById={nameById} />
          {selectedRun.diagnostics && (
            <RunDiagnostics
              diagnostics={selectedRun.diagnostics}
              nameById={nameById}
              shiftTypeNameByCode={shiftTypeNameByCode}
              onJumpToDate={onJumpToDate}
            />
          )}
          <div className="flex items-center gap-2">
            {selectedRun.reverted_at ? (
              <p className="text-xs text-muted-foreground">
                {t("generate.revertedBadge", {
                  date: new Date(selectedRun.reverted_at).toLocaleString(),
                })}
              </p>
            ) : (
              <RevertButton
                pending={revertPendingId === selectedRun.id}
                onRevert={() => void handleRevert(selectedRun.id)}
              />
            )}
          </div>
          {revertError !== null && <ApiErrorText error={revertError} />}
        </div>
      )}

      {historyQuery.isLoading && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {historyQuery.error !== null && historyQuery.error !== undefined && (
        <ApiErrorText error={historyQuery.error} />
      )}
      {runs.length > 0 && (
        <RunHistory runs={runs} selectedRunId={selectedRunId} onSelect={setSelectedRunId} />
      )}
    </div>
  );
}

function RevertButton({ pending, onRevert }: { pending: boolean; onRevert: () => void }) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);

  if (!confirming) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={() => setConfirming(true)}>
        {t("generate.revertButton")}
      </Button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-300 bg-amber-50 p-2">
      <span className="text-sm text-amber-900">{t("generate.revertConfirm")}</span>
      <Button type="button" size="sm" disabled={pending} onClick={onRevert}>
        {t("common.confirm")}
      </Button>
      <Button type="button" size="sm" variant="secondary" onClick={() => setConfirming(false)}>
        {t("common.cancel")}
      </Button>
    </div>
  );
}

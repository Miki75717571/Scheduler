import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import type { Assignment, ScheduleViolation, ShiftSlot } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { fetchShiftTypes } from "../features/availability/api";
import { fetchPeriod, fetchSlots, fetchTracker, updatePeriodState } from "../features/manager/api";
import {
  createAssignment,
  fetchAssignments,
  fetchAvailableEmployees,
  fetchViolations,
  moveAssignment,
  removeAssignment,
  setAssignmentLock,
} from "../features/schedule/api";
import { AssignPickerDialog } from "../features/schedule/AssignPickerDialog";
import { EmployeeFilter } from "../features/schedule/EmployeeFilter";
import { ManagerMonthGrid } from "../features/schedule/ManagerMonthGrid";
import { PublishBar } from "../features/schedule/PublishBar";
import type { ViolationJumpTarget } from "../features/schedule/ViolationsPanel";
import { ViolationsPanel } from "../features/schedule/ViolationsPanel";
import { useAuth } from "../lib/auth-context";

function monthLabel(year: number, month: number, language: string): string {
  return new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
}

export function ManagerSchedulePage() {
  const { periodId } = useParams<{ periodId: string }>();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [pickerSlot, setPickerSlot] = useState<ShiftSlot | null>(null);
  const [pickPending, setPickPending] = useState<string | null>(null);
  const [pickError, setPickError] = useState<unknown>(null);
  const [highlightedDate, setHighlightedDate] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<unknown>(null);
  const [undoState, setUndoState] = useState<Assignment | null>(null);
  const undoTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const periodQuery = useQuery({
    queryKey: ["period", periodId],
    queryFn: () => fetchPeriod(periodId as string),
    enabled: Boolean(periodId),
  });
  const slotsQuery = useQuery({
    queryKey: ["period-slots", periodId],
    queryFn: () => fetchSlots(periodId as string),
    enabled: Boolean(periodId),
  });
  const shiftTypesQuery = useQuery({ queryKey: ["shift-types"], queryFn: fetchShiftTypes });
  const rosterQuery = useQuery({
    queryKey: ["tracker", periodId],
    queryFn: () => fetchTracker(periodId as string),
    enabled: Boolean(periodId),
  });
  const assignmentsQuery = useQuery({
    queryKey: ["assignments", periodId],
    queryFn: () => fetchAssignments(periodId as string),
    enabled: Boolean(periodId),
  });
  const violationsQuery = useQuery({
    queryKey: ["violations", periodId],
    queryFn: () => fetchViolations(periodId as string),
    enabled: Boolean(periodId),
  });
  const availableEmployeesQuery = useQuery({
    queryKey: ["available-employees", periodId, pickerSlot?.id],
    queryFn: () => fetchAvailableEmployees(periodId as string, pickerSlot!.id),
    enabled: Boolean(periodId && pickerSlot),
  });

  if (!periodId) return null;
  // useParams() types every param as possibly-undefined regardless of the
  // generic hint above, and TS doesn't retain the `if` guard's narrowing
  // inside the function declarations below - `pid` carries the narrowed
  // type through them without an `as string` at every call site.
  const pid: string = periodId;

  const assignments = assignmentsQuery.data ?? [];
  const violations = violationsQuery.data ?? [];
  const roster = (rosterQuery.data ?? []).map((entry) => ({
    user_id: entry.user_id,
    full_name: entry.full_name,
  }));
  const nameById = Object.fromEntries(roster.map((r) => [r.user_id, r.full_name]));
  const dateBySlotId = Object.fromEntries((slotsQuery.data ?? []).map((s) => [s.id, s.date]));
  const shiftTypesById = Object.fromEntries((shiftTypesQuery.data ?? []).map((st) => [st.id, st]));

  function setAssignmentsCache(updater: (old: Assignment[]) => Assignment[]) {
    queryClient.setQueryData<Assignment[]>(["assignments", pid], (old) => updater(old ?? []));
  }

  function applyMutationResult(result: { violations: ScheduleViolation[] }) {
    queryClient.setQueryData(["violations", pid], result.violations);
  }

  async function handlePick(userId: string) {
    if (!pickerSlot || !user) return;
    setPickPending(userId);
    setPickError(null);
    const tempId = `temp-${crypto.randomUUID()}`;
    const optimistic: Assignment = {
      id: tempId,
      shift_slot_id: pickerSlot.id,
      user_id: userId,
      full_name: nameById[userId] ?? "",
      source: "MANUAL",
      is_locked: false,
      modified_after_publish: periodQuery.data?.state === "PUBLISHED",
      created_by_user_id: user.id,
      created_at: new Date().toISOString(),
      updated_at: null,
    };
    setAssignmentsCache((old) => [...old, optimistic]);
    try {
      const result = await createAssignment(pid, { shift_slot_id: pickerSlot.id, user_id: userId });
      setAssignmentsCache((old) => old.map((a) => (a.id === tempId ? (result.assignment as Assignment) : a)));
      applyMutationResult(result);
      setPickerSlot(null);
    } catch (error) {
      setAssignmentsCache((old) => old.filter((a) => a.id !== tempId));
      setPickError(error);
    } finally {
      setPickPending(null);
    }
  }

  async function handleRemove(assignment: Assignment) {
    clearTimeout(undoTimerRef.current);
    setAssignmentsCache((old) => old.filter((a) => a.id !== assignment.id));
    setMutationError(null);
    try {
      const result = await removeAssignment(pid, assignment.id);
      applyMutationResult(result);
      setUndoState(assignment);
      undoTimerRef.current = setTimeout(() => setUndoState(null), 8000);
    } catch (error) {
      setAssignmentsCache((old) => [...old, assignment]);
      setMutationError(error);
    }
  }

  async function handleUndoRemove() {
    if (!undoState) return;
    const removed = undoState;
    setUndoState(null);
    clearTimeout(undoTimerRef.current);
    const tempId = `temp-undo-${crypto.randomUUID()}`;
    setAssignmentsCache((old) => [...old, { ...removed, id: tempId }]);
    try {
      const result = await createAssignment(pid, {
        shift_slot_id: removed.shift_slot_id,
        user_id: removed.user_id,
        is_locked: removed.is_locked,
      });
      setAssignmentsCache((old) => old.map((a) => (a.id === tempId ? (result.assignment as Assignment) : a)));
      applyMutationResult(result);
    } catch (error) {
      setAssignmentsCache((old) => old.filter((a) => a.id !== tempId));
      setMutationError(error);
    }
  }

  async function handleMove(assignmentId: string, targetSlotId: string) {
    const previous = assignments.find((a) => a.id === assignmentId);
    if (!previous || previous.is_locked) return;
    setAssignmentsCache((old) =>
      old.map((a) => (a.id === assignmentId ? { ...a, shift_slot_id: targetSlotId } : a)),
    );
    setMutationError(null);
    try {
      const result = await moveAssignment(pid, assignmentId, targetSlotId);
      setAssignmentsCache((old) =>
        old.map((a) => (a.id === assignmentId ? (result.assignment as Assignment) : a)),
      );
      applyMutationResult(result);
    } catch (error) {
      setAssignmentsCache((old) => old.map((a) => (a.id === assignmentId ? previous : a)));
      setMutationError(error);
    }
  }

  async function handleToggleLock(assignment: Assignment) {
    const nextLocked = !assignment.is_locked;
    setAssignmentsCache((old) =>
      old.map((a) => (a.id === assignment.id ? { ...a, is_locked: nextLocked } : a)),
    );
    setMutationError(null);
    try {
      const updated = await setAssignmentLock(pid, assignment.id, nextLocked);
      setAssignmentsCache((old) => old.map((a) => (a.id === assignment.id ? updated : a)));
    } catch (error) {
      setAssignmentsCache((old) => old.map((a) => (a.id === assignment.id ? assignment : a)));
      setMutationError(error);
    }
  }

  async function handlePublish(overrideViolations: boolean) {
    await updatePeriodState(pid, "PUBLISHED", overrideViolations);
    await queryClient.invalidateQueries({ queryKey: ["period", pid] });
    await queryClient.invalidateQueries({ queryKey: ["periods"] });
  }

  function handleJump(target: ViolationJumpTarget) {
    if (target.date) {
      setHighlightedDate(target.date);
      document
        .getElementById(`schedule-day-${target.date}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => setHighlightedDate(null), 3000);
    } else if (target.userId) {
      setSelectedEmployeeId(target.userId);
    }
  }

  const loading =
    periodQuery.isLoading ||
    slotsQuery.isLoading ||
    shiftTypesQuery.isLoading ||
    rosterQuery.isLoading ||
    assignmentsQuery.isLoading ||
    violationsQuery.isLoading;
  const firstError =
    periodQuery.error ??
    slotsQuery.error ??
    shiftTypesQuery.error ??
    rosterQuery.error ??
    assignmentsQuery.error ??
    violationsQuery.error;

  if (loading) {
    return <p className="text-sm text-muted-foreground">{t("schedule.loading")}</p>;
  }
  if (firstError || !periodQuery.data) {
    return <ApiErrorText error={firstError} />;
  }

  const period = periodQuery.data;
  const slots = slotsQuery.data ?? [];
  const errorCount = violations.filter((v) => v.severity === "ERROR").length;
  const modifiedAfterPublishCount = assignments.filter((a) => a.modified_after_publish).length;
  const selectedEmployeeShiftCount = selectedEmployeeId
    ? assignments.filter((a) => a.user_id === selectedEmployeeId).length
    : 0;

  const pickerShiftType = pickerSlot ? shiftTypesById[pickerSlot.shift_type_id] : null;
  const pickerAssignedUserIds = pickerSlot
    ? new Set(assignments.filter((a) => a.shift_slot_id === pickerSlot.id).map((a) => a.user_id))
    : new Set<string>();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">
            {t("schedule.title", { month: monthLabel(period.year, period.month, i18n.language) })}
          </h1>
          <Link
            to={`/manager/periods/${periodId}`}
            className="text-xs text-muted-foreground hover:text-foreground print:hidden"
          >
            ← {t("manager.periodsTitle")}
          </Link>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <Button type="button" variant="secondary" size="sm" onClick={() => window.print()}>
            {t("schedule.printButton")}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <EmployeeFilter
          roster={roster}
          selectedEmployeeId={selectedEmployeeId}
          shiftCount={selectedEmployeeShiftCount}
          onChange={setSelectedEmployeeId}
        />
      </div>

      {mutationError !== null && <ApiErrorText error={mutationError} />}

      {undoState && (
        <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm print:hidden">
          <span>
            {t("schedule.removedNotice", {
              name: undoState.full_name,
              shift: shiftTypesById[slots.find((s) => s.id === undoState.shift_slot_id)?.shift_type_id ?? ""]
                ?.code,
              date: dateBySlotId[undoState.shift_slot_id],
            })}
          </span>
          <Button type="button" size="sm" variant="secondary" onClick={() => void handleUndoRemove()}>
            {t("schedule.undoRemove")}
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <ManagerMonthGrid
          year={period.year}
          month={period.month}
          slots={slots}
          shiftTypes={shiftTypesQuery.data ?? []}
          assignments={assignments}
          violations={violations}
          selectedEmployeeId={selectedEmployeeId}
          highlightedDate={highlightedDate}
          onAddClick={setPickerSlot}
          onToggleLock={(a) => void handleToggleLock(a)}
          onRemove={(a) => void handleRemove(a)}
          onMove={(assignmentId, targetSlotId) => void handleMove(assignmentId, targetSlotId)}
        />

        <div className="space-y-4">
          <PublishBar
            periodState={period.state}
            publishedAt={period.published_at}
            totalSlots={slots.length}
            totalAssignments={assignments.length}
            errorCount={errorCount}
            modifiedAfterPublishCount={modifiedAfterPublishCount}
            onPublish={handlePublish}
          />
          <ViolationsPanel
            violations={violations}
            nameById={nameById}
            dateBySlotId={dateBySlotId}
            onJump={handleJump}
          />
        </div>
      </div>

      {pickerSlot && pickerShiftType && (
        <AssignPickerDialog
          shiftTypeName={i18n.language === "pl" ? pickerShiftType.name_pl : pickerShiftType.name_en}
          dateLabel={new Date(pickerSlot.date).toLocaleDateString(i18n.language === "pl" ? "pl-PL" : "en-US", {
            day: "numeric",
            month: "short",
          })}
          roster={roster}
          assignedUserIds={pickerAssignedUserIds}
          candidates={availableEmployeesQuery.data ?? []}
          loading={availableEmployeesQuery.isLoading}
          error={pickError ?? availableEmployeesQuery.error}
          pendingUserId={pickPending}
          onPick={(userId) => void handlePick(userId)}
          onClose={() => {
            setPickerSlot(null);
            setPickError(null);
          }}
        />
      )}
    </div>
  );
}

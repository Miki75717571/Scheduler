import { useCallback, useEffect, useRef, useState } from "react";

export type SaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Debounces `value` and persists it via `save`. Concurrent edits while a
 * save is in flight are coalesced into a single follow-up save (never
 * dropped, never sent out of order) rather than firing one request per
 * keystroke/tap.
 */
export function useAutosave<T>(
  value: T,
  save: (value: T) => Promise<void>,
  delayMs: number,
): { status: SaveStatus; retry: () => void } {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const isFirstRender = useRef(true);
  const savingRef = useRef(false);
  const pendingRef = useRef<T | null>(null);
  const autoRetriedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const flush = useCallback(
    (next: T) => {
      if (savingRef.current) {
        pendingRef.current = next;
        return;
      }
      savingRef.current = true;
      setStatus("saving");
      save(next)
        .then(() => {
          autoRetriedRef.current = false;
          setStatus("saved");
        })
        .catch(() => {
          setStatus("error");
          if (!autoRetriedRef.current) {
            autoRetriedRef.current = true;
            setTimeout(() => flush(next), 4000);
          }
        })
        .finally(() => {
          savingRef.current = false;
          if (pendingRef.current !== null) {
            const next2 = pendingRef.current;
            pendingRef.current = null;
            flush(next2);
          }
        });
    },
    [save],
  );

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => flush(value), delayMs);
    return () => clearTimeout(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, delayMs]);

  const retry = useCallback(() => {
    autoRetriedRef.current = false;
    flush(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flush, value]);

  return { status, retry };
}

import { useCallback, useRef, useState } from "react";

/**
 * Guards a form submission: ``run(task)`` ignores calls while a previous task is still in flight (a double click
 * cannot create two records) and exposes ``busy`` to disable the Save button. The ref is checked synchronously, so
 * it does not depend on React having re-rendered between two clicks.
 */
export function useBusy(): { busy: boolean; run: (task: () => Promise<unknown>) => void } {
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const run = useCallback((task: () => Promise<unknown>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    task().finally(() => {
      inFlight.current = false;
      setBusy(false);
    });
  }, []);
  return { busy, run };
}

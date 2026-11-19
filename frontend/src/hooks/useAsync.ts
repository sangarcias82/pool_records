import { useEffect, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  /** The raw error (``<Loaded>`` turns it into text in the current language). */
  error: unknown;
}

/** Load data when ``deps`` change; ignores results of stale requests. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null });
  useEffect(() => {
    let stale = false;
    load().then(
      (data) => !stale && setState({ data, error: null }),
      (err: unknown) => !stale && setState({ data: null, error: err ?? new Error("unknown error") }),
    );
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

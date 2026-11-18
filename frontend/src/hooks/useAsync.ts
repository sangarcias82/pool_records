import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
}

/** Load data when ``deps`` change; ignores results of stale requests. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null });
  useEffect(() => {
    let stale = false;
    load().then(
      (data) => !stale && setState({ data, error: null }),
      (err: unknown) => !stale && setState({ data: null, error: errorMessage(err) }),
    );
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

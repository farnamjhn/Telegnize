import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./api";

export interface AsyncState<T> {
  data: T | undefined;
  error: string | undefined;
  /** First load, with nothing to show yet. */
  loading: boolean;
  /** A later load, while the previous render is still on screen. */
  refetching: boolean;
  reload: () => void;
  setData: (next: T) => void;
}

/**
 * Runs `task` whenever `deps` change, keeping the last successful value on
 * screen while the next one loads — no skeleton flash, no layout jump.
 *
 * Returning `null` from `task` skips the call (nothing is selected yet).
 */
export function useAsync<T>(
  task: () => Promise<T> | null,
  deps: readonly unknown[],
): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);
  const [nonce, setNonce] = useState(0);
  const latest = useRef(0);
  const taskRef = useRef(task);
  taskRef.current = task;

  useEffect(() => {
    const promise = taskRef.current();
    if (promise === null) {
      setData(undefined);
      setError(undefined);
      setPending(false);
      return;
    }

    const ticket = ++latest.current;
    setPending(true);
    promise.then(
      (value) => {
        if (ticket !== latest.current) return;
        setData(value);
        setError(undefined);
        setPending(false);
      },
      (cause: unknown) => {
        if (ticket !== latest.current) return;
        setError(cause instanceof ApiError ? cause.message : String(cause));
        setPending(false);
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return {
    data,
    error,
    loading: pending && data === undefined,
    refetching: pending && data !== undefined,
    reload,
    setData,
  };
}

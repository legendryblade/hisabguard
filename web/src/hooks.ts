import { createContext, useContext, useEffect, useRef, useState } from 'react';

export const AuthRevision = createContext(0);

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, key: string = '') {
  const authRevision = useContext(AuthRevision);
  const loader = useRef(load);
  loader.current = load;
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>({ data: null, loading: true, error: null });
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    setState({ data: null, loading: true, error: null });
    loader.current(abort.signal).then((data) => {
      if (!abort.signal.aborted) setState({ data, loading: false, error: null });
    }).catch((error: unknown) => {
      if (!abort.signal.aborted) setState({ data: null, loading: false, error: error instanceof Error ? error.message : 'Unable to load. Please retry.' });
    });
    return () => abort.abort();
  }, [key, revision, authRevision]);
  return {
    ...state,
    reload: () => { controller.current?.abort(); setRevision((value) => value + 1); },
    replace: (data: T) => { controller.current?.abort(); setState({ data, loading: false, error: null }); },
  };
}

export function useTask() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const active = useRef<AbortController | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; active.current?.abort(); }; }, []);
  async function run<T>(work: (signal: AbortSignal) => Promise<T>, onSuccess?: (data: T) => void, onFailure?: (error: unknown, signal: AbortSignal) => Promise<void> | void): Promise<boolean> {
    if (active.current) return false;
    const abort = new AbortController();
    active.current = abort;
    setBusy(true); setError(null); setNotice(null);
    try {
      const data = await work(abort.signal);
      if (alive.current && !abort.signal.aborted) onSuccess?.(data);
      return !abort.signal.aborted;
    } catch (error: unknown) {
      if (alive.current && !abort.signal.aborted) {
        setError(error instanceof Error ? error.message : 'The request failed. Please retry.');
        try { await onFailure?.(error, abort.signal); } catch { /* Preserve the original actionable API error if recovery also fails. */ }
      }
      return false;
    } finally {
      if (active.current === abort) active.current = null;
      if (alive.current) setBusy(false);
    }
  }
  return { busy, error, notice, run, setError, setNotice };
}

// Minimal server-state cache (TanStack Query-style): keyed cache, dedupe,
// stale-while-revalidate, invalidation by key prefix, polling.
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { api, ApiError } from './api';

type Entry = { data?: unknown; error?: ApiError; status: 'idle' | 'loading' | 'success' | 'error'; at: number; p?: Promise<void> };
const cache = new Map<string, Entry>();
const subs = new Map<string, Set<() => void>>();

function emit(key: string) {
  subs.get(key)?.forEach((f) => f());
}

function fetchKey(key: string, force = false): Promise<void> {
  const e = cache.get(key) ?? { status: 'idle', at: 0 };
  if (e.p && !force) return e.p;
  const p = api(key)
    .then((data) => { cache.set(key, { data, status: 'success', at: Date.now() }); })
    .catch((error: ApiError) => { cache.set(key, { ...cache.get(key), error, status: 'error', at: Date.now(), p: undefined }); })
    .finally(() => emit(key));
  cache.set(key, { ...e, status: e.data === undefined ? 'loading' : e.status, p });
  emit(key);
  return p;
}

export function invalidate(prefix: string) {
  for (const k of cache.keys()) if (k.startsWith(prefix)) { const e = cache.get(k)!; e.at = 0; if (subs.get(k)?.size) fetchKey(k, true); }
}

export function useQuery<T = any>(key: string | null, opts: { poll?: number; staleMs?: number } = {}) {
  const sub = useCallback((f: () => void) => {
    if (!key) return () => {};
    if (!subs.has(key)) subs.set(key, new Set());
    subs.get(key)!.add(f);
    return () => subs.get(key)!.delete(f);
  }, [key]);
  const snap = useSyncExternalStore(sub, () => (key ? cache.get(key) : undefined), () => undefined);
  useEffect(() => {
    if (!key) return;
    const e = cache.get(key);
    if (!e || Date.now() - e.at > (opts.staleMs ?? 15000)) fetchKey(key);
    if (!opts.poll) return;
    const t = setInterval(() => fetchKey(key, true), opts.poll);
    return () => clearInterval(t);
  }, [key, opts.poll, opts.staleMs]);
  return {
    data: snap?.data as T | undefined,
    error: snap?.error,
    loading: !!key && (!snap || snap.status === 'loading' || (snap.status === 'idle')),
    refetch: () => key && fetchKey(key, true),
  };
}

export function useMutation<A, R = any>(fn: (a: A) => Promise<R>, opts: { invalidates?: string[]; onSuccess?: (r: R) => void; onError?: (e: ApiError) => void } = {}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  const mutate = async (a: A) => {
    setPending(true);
    setError(null);
    try {
      const r = await fn(a);
      opts.invalidates?.forEach(invalidate);
      opts.onSuccess?.(r);
      return r;
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, 'error', String(e));
      if (alive.current) setError(err);
      opts.onError?.(err);
      return undefined;
    } finally {
      if (alive.current) setPending(false);
    }
  };
  return { mutate, pending, error };
}

export function clearCache() {
  cache.clear();
}

// Typed fetch wrapper. All errors surface as ApiError with the server's code.
import { auth } from './store';

export const API = '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal };

let refreshing: Promise<boolean> | null = null;

/** Exchange the refresh token for a new pair once; concurrent 401s share one refresh. */
function tryRefresh(): Promise<boolean> {
  const refresh = auth.get().refresh;
  if (!refresh) return Promise.resolve(false);
  refreshing ??= fetch(API + '/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refresh }) })
    .then(async (r) => {
      if (!r.ok) return false;
      const d = await r.json();
      auth.setTokens(d.access_token, d.refresh_token ?? null);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T = any>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  const token = auth.get().token;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(API + path, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'offline', 'Cannot reach the ISL NOVA server. Check your connection.');
  }
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = data?.error ?? {};
    if (res.status === 401 && token && err.code === 'invalid_token') {
      if (!retried && await tryRefresh()) return api<T>(path, opts, true);
      auth.logout();
    }
    throw new ApiError(res.status, err.code ?? 'http_error', err.message ?? res.statusText, err.details);
  }
  return data as T;
}

function safeJson(t: string) {
  try { return JSON.parse(t); } catch { return null; }
}

export const qs = (o: Record<string, unknown>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : '';
};

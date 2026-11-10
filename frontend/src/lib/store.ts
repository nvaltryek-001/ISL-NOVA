// Tiny external stores built on useSyncExternalStore (Zustand-like API).
import { useSyncExternalStore } from 'react';

export function createStore<T>(initial: T) {
  let state = initial;
  const subs = new Set<() => void>();
  return {
    get: () => state,
    set(patch: Partial<T> | ((s: T) => Partial<T>)) {
      const p = typeof patch === 'function' ? (patch as (s: T) => Partial<T>)(state) : patch;
      state = { ...state, ...p };
      subs.forEach((f) => f());
    },
    subscribe(f: () => void) {
      subs.add(f);
      return () => subs.delete(f);
    },
  };
}

export function useStore<T, S>(store: ReturnType<typeof createStore<T>>, sel: (s: T) => S): S {
  return useSyncExternalStore(store.subscribe, () => sel(store.get()), () => sel(store.get()));
}

export type User = {
  id: number; email: string; display_name: string; roles: string[]; preferred_language: 'en' | 'hi' | 'kn';
  settings: Record<string, unknown>; two_factor?: boolean;
};

const KEY = 'isl-nova-session';

type Session = { token: string | null; refresh: string | null; user: User | null };

function load(): Session {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return { refresh: null, ...JSON.parse(raw) };
  } catch { /* storage unavailable */ }
  return { token: null, refresh: null, user: null };
}

function save(s: Session) {
  try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* ignore */ }
}

const authStore = createStore(load());

export const auth = {
  ...authStore,
  login(token: string, user: User, refresh: string | null = null) {
    authStore.set({ token, user, refresh });
    save({ token, user, refresh });
  },
  setUser(user: User) {
    authStore.set({ user });
    save({ ...authStore.get(), user });
  },
  setTokens(token: string, refresh: string | null) {
    authStore.set({ token, refresh });
    save({ ...authStore.get(), token, refresh });
  },
  logout() {
    const refresh = authStore.get().refresh;
    authStore.set({ token: null, user: null, refresh: null });
    try { sessionStorage.removeItem(KEY); } catch { /* ignore */ }
    // revoke the refresh token on the server too (best effort, no await)
    if (refresh) fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refresh }) }).catch(() => undefined);
  },
};

export const useAuth = () => useStore(authStore, (s) => s);

export const PERMS: Record<string, string[]> = {
  'signs:write': ['admin', 'linguist'],
  'signs:review': ['admin', 'linguist'],
  'translations:write': ['admin', 'linguist'],
  'dataset:read': ['admin', 'linguist', 'data_curator', 'researcher'],
  'dataset:write': ['admin', 'data_curator'],
  'dataset:review': ['admin', 'linguist'],
  'dataset:version': ['admin', 'data_curator'],
  'experiments:read': ['admin', 'researcher', 'data_curator'],
  'experiments:write': ['admin', 'researcher'],
  'models:promote': ['admin'],
  'feedback:read': ['admin', 'linguist'],
  'phrases:quick': ['admin', 'linguist'],
  'admin:users': ['admin'],
  'classes:manage': ['admin', 'teacher'],
  'analytics:read': ['admin', 'researcher'],
};

/** UI hint only - the server enforces every permission. */
export function can(user: User | null, perm: string) {
  return !!user && user.roles.some((r) => PERMS[perm]?.includes(r));
}

export type Theme = 'light' | 'dark' | 'system';
export type Prefs = { theme: Theme; highContrast: boolean; reducedMotion: boolean; largeText: boolean; speechRate: number; language: 'en' | 'hi' | 'kn' };

function loadPrefs(): Prefs {
  const d: Prefs = { theme: 'light', highContrast: false, reducedMotion: false, largeText: false, speechRate: 1, language: 'en' };
  try { return { ...d, ...JSON.parse(localStorage.getItem('isl-nova-prefs') || '{}') }; } catch { return d; }
}

export const prefs = createStore<Prefs>(loadPrefs());
prefs.subscribe(() => {
  const p = prefs.get();
  try { localStorage.setItem('isl-nova-prefs', JSON.stringify(p)); } catch { /* ignore */ }
  applyPrefs(p);
});

export function applyPrefs(p: Prefs) {
  if (typeof document === 'undefined') return;
  const c = document.documentElement.classList;
  c.toggle('dark', resolvedTheme(p.theme) === 'dark');
  c.toggle('hc', p.highContrast);
  c.toggle('reduce-motion', p.reducedMotion);
  c.toggle('large-text', p.largeText);
  document.documentElement.lang = p.language === 'hi' ? 'hi' : p.language === 'kn' ? 'kn' : 'en';
}

export const usePrefs = () => useStore(prefs, (s) => s);

export function resolvedTheme(t: Theme): 'light' | 'dark' {
  if (t !== 'system') return t;
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
if (typeof matchMedia !== 'undefined') {
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => prefs.get().theme === 'system' && applyPrefs(prefs.get()));
}

export type Toast = { id: number; kind: 'ok' | 'error' | 'info'; text: string };
export const toasts = createStore<{ items: Toast[] }>({ items: [] });
let tid = 0;
export function toast(text: string, kind: Toast['kind'] = 'ok') {
  const id = ++tid;
  toasts.set((s) => ({ items: [...s.items, { id, kind, text }] }));
  setTimeout(() => toasts.set((s) => ({ items: s.items.filter((t) => t.id !== id) })), 4200);
}

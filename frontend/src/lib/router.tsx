// Small History-API router: pattern matching with :params, Link, navigate.
import { type AnchorHTMLAttributes, type ReactNode, useSyncExternalStore } from 'react';

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((f) => f());
if (typeof window !== 'undefined') window.addEventListener('popstate', notify);

export function navigate(to: string, replace = false) {
  if (replace) history.replaceState(null, '', to);
  else history.pushState(null, '', to);
  notify();
  if (!to.includes('#')) window.scrollTo({ top: 0 });
}

const getPath = () => (typeof window === 'undefined' ? '/' : window.location.pathname + window.location.search);

export function useLocation() {
  const full = useSyncExternalStore((f) => { listeners.add(f); return () => listeners.delete(f); }, getPath, () => '/');
  const [pathname, search = ''] = full.split('?');
  return { pathname, search: new URLSearchParams(search) };
}

export function match(pattern: string, path: string): Record<string, string> | null {
  const a = pattern.split('/').filter(Boolean);
  const b = path.split('/').filter(Boolean);
  if (a.length !== b.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < a.length; i++) {
    if (a[i].startsWith(':')) params[a[i].slice(1)] = decodeURIComponent(b[i]);
    else if (a[i] !== b[i]) return null;
  }
  return params;
}

export type RouteDef = { path: string; render: (p: Record<string, string>) => ReactNode };

export function Routes({ routes, fallback }: { routes: RouteDef[]; fallback: ReactNode }) {
  const { pathname } = useLocation();
  for (const r of routes) {
    const p = match(r.path, pathname);
    if (p) return <>{r.render(p)}</>;
  }
  return <>{fallback}</>;
}

export function Link({ to, children, ...rest }: { to: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  const { pathname } = useLocation();
  const current = pathname === to || (to !== '/' && pathname.startsWith(to + '/'));
  return (
    <a
      href={to}
      aria-current={current ? 'page' : undefined}
      onClick={(e) => {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || rest.target) return;
        e.preventDefault();
        navigate(to);
      }}
      {...rest}
    >
      {children}
    </a>
  );
}

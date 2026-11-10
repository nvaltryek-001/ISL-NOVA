import clsx from 'clsx';
import { type ReactNode, useEffect, useState } from 'react';
import { Icon, type IconName } from './components/icons';
import { Badge, Button, Toasts } from './components/ui';
import { clearCache, useQuery } from './lib/query';
import { Link, navigate, Routes, useLocation } from './lib/router';
import { auth, can, prefs, resolvedTheme, useAuth, usePrefs } from './lib/store';
import { type Lang, LANG_NAMES, useT } from './i18n';
import { AdminPage } from './pages/Admin';
import { AILabPage } from './pages/AILab';
import { AcademyPage } from './pages/Academy';
import { AuthPage } from './pages/Auth';
import { CommunicatePage } from './pages/Communicate';
import { DashboardPage } from './pages/Dashboard';
import { DatasetLabPage } from './pages/DatasetLab';
import { ExplorerPage, SignDetailPage } from './pages/Explorer';
import { KioskPage } from './pages/Kiosk';
import { LivePage } from './pages/Live';
import { ResearchPage } from './pages/Research';
import { SettingsPage } from './pages/Settings';
import { VideoAnalysisPage } from './pages/VideoAnalysis';
import { VizPage } from './pages/Viz3D';

type Nav = { to: string; label: string; icon: IconName; perm?: string };
const NAV: { group: string; items: Nav[] }[] = [
  { group: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: 'dashboard' }] },
  { group: 'Recognise', items: [
    { to: '/live', label: 'Live Recognition', icon: 'camera' },
    { to: '/analysis', label: 'Video Analysis', icon: 'film' },
  ] },
  { group: 'Learn & communicate', items: [
    { to: '/signs', label: 'Sign Explorer', icon: 'book' },
    { to: '/communicate', label: 'Communication', icon: 'chat' },
    { to: '/academy', label: 'Learning Academy', icon: 'cap' },
  ] },
  { group: 'Data & AI', items: [
    { to: '/dataset', label: 'Dataset Lab', icon: 'database' },
    { to: '/ai', label: 'AI Laboratory', icon: 'cpu' },
    { to: '/research', label: 'Research Centre', icon: 'flask' },
    { to: '/viz', label: '3D Visualisation', icon: 'cube' },
  ] },
  { group: 'Operate', items: [
    { to: '/admin', label: 'Administration', icon: 'shield', perm: 'admin:users' },
    { to: '/kiosk', label: 'Kiosk mode', icon: 'kiosk' },
  ] },
];

function ModelPill() {
  const { data } = useQuery<{ available: boolean; synthetic?: boolean; n_classes?: number }>('/model/info', { poll: 60000 });
  const t = useT();
  if (!data) return null;
  return (
    <Link to="/ai" className="hidden sm:block" title={t('Recognition model status')}>
      {data.available
        ? <Badge tone={data.synthetic ? 'warn' : 'ok'}>{data.synthetic ? 'Synthetic test model' : `${t('Model live')} · ${data.n_classes} ${t('signs')}`}</Badge>
        : <Badge tone="bad"><span className="size-1.5 rounded-full bg-current" />{t('No trained model')}</Badge>}
    </Link>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const t = useT();
  return (
    <nav aria-label="Main" className="flex h-full flex-col gap-6 overflow-y-auto px-3 py-5">
      <Link to="/" className="flex items-center gap-3 px-2" onClick={onNavigate}>
        <img src="/favicon.svg" alt="" className="size-9" />
        <span>
          <span className="block font-display text-[17px] font-semibold tracking-tight text-fg">ISL NOVA</span>
          <span className="block text-[11px] text-ink-400">{t('Beyond gestures. Towards understanding.')}</span>
        </span>
      </Link>
      {NAV.map((g) => {
        const items = g.items.filter((i) => !i.perm || can(user, i.perm));
        if (!items.length) return null;
        return (
          <div key={g.group}>
            <p className="label mb-1.5 px-3 text-[10px]">{t(g.group)}</p>
            <ul className="space-y-0.5">
              {items.map((i) => (
                <li key={i.to}><Link to={i.to} className="nav-link" onClick={onNavigate}><Icon name={i.icon} />{t(i.label)}</Link></li>
              ))}
            </ul>
          </div>
        );
      })}
      <div className="mt-auto rounded-xl border border-ink-700 bg-ink-800 p-3 text-xs text-ink-400">
        {t('Vocabulary entries are derived from the INCLUDE dataset (CC BY 4.0) and await qualified ISL review.')}
      </div>
    </nav>
  );
}

function LanguageSwitcher() {
  const p = usePrefs();
  const t = useT();
  return (
    <select aria-label={t('Interface language')} title={t('Interface language')} value={p.language}
      onChange={(e) => prefs.set({ language: e.target.value as Lang })}
      className="h-9 rounded-lg border border-ink-700 bg-ink-850 px-2 text-sm text-ink-100">
      {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l} lang={l}>{LANG_NAMES[l]}</option>)}
    </select>
  );
}

function ThemeToggle() {
  const p = usePrefs();
  const dark = resolvedTheme(p.theme) === 'dark';
  return (
    <button className="rounded-lg p-2 text-ink-300 hover:bg-ink-800 hover:text-fg" aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={dark ? 'Light theme' : 'Dark theme'} onClick={() => prefs.set({ theme: dark ? 'light' : 'dark' })}>
      <Icon name={dark ? 'sun' : 'moon'} />
    </button>
  );
}

function UserMenu() {
  const { user } = useAuth();
  const { data: notes } = useQuery<{ id: number; read_at: string | null }[]>(user ? '/notifications' : null, { poll: 60000 });
  if (!user) return <Button size="sm" variant="primary" icon="user" onClick={() => navigate('/login')}>Sign in</Button>;
  const unread = notes?.filter((n) => !n.read_at).length ?? 0;
  return (
    <div className="flex items-center gap-1">
      <Link to="/settings" className="relative rounded-lg p-2 text-ink-300 hover:bg-ink-800 hover:text-fg" aria-label={`Settings and notifications${unread ? `, ${unread} unread` : ''}`}>
        <Icon name="bell" />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-signal" />}
      </Link>
      <Link to="/settings" className="hidden items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-800 md:flex">
        <span className="grid size-7 place-items-center rounded-full bg-gradient-to-br from-nova-500 to-indigo-glow text-xs font-semibold text-white">{user.display_name.slice(0, 1).toUpperCase()}</span>
        <span className="text-left leading-tight"><span className="block text-sm text-fg">{user.display_name}</span><span className="block text-[11px] text-ink-400">{user.roles.join(', ')}</span></span>
      </Link>
      <button className="rounded-lg p-2 text-ink-400 hover:bg-ink-800 hover:text-fg" aria-label="Sign out" title="Sign out"
        onClick={() => { auth.logout(); clearCache(); navigate('/'); }}><Icon name="logout" /></button>
    </div>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-nova-500 focus:px-3 focus:py-2">Skip to content</a>
      <aside className="sticky top-0 hidden h-dvh border-r border-ink-700 bg-ink-850/70 backdrop-blur lg:block"><Sidebar /></aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink-950/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-ink-700 bg-ink-850"><Sidebar onNavigate={() => setOpen(false)} /></aside>
        </div>
      )}
      <div className="min-w-0">
        <header className="surface-glass sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-ink-700 px-4 md:px-8">
          <button className="rounded-lg p-2 text-ink-300 hover:bg-ink-800 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Icon name="menu" /></button>
          <button onClick={() => navigate('/signs')} className="flex h-9 min-w-0 max-w-sm flex-1 items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 text-sm text-ink-400 shadow-sm hover:border-ink-600">
            <Icon name="search" size={16} /><span className="truncate">Search signs in English, हिन्दी, ಕನ್ನಡ…</span>
          </button>
          <div className="ml-auto flex shrink-0 items-center gap-2"><ModelPill /><LanguageSwitcher /><ThemeToggle /><UserMenu /></div>
        </header>
        <main id="main" className="mx-auto max-w-[1400px] px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <div className="grid place-items-center py-24 text-center">
      <p className="font-display text-6xl font-semibold text-ink-600">404</p>
      <p className="mt-3 text-lg text-fg">This page does not exist.</p>
      <Button className="mt-6" onClick={() => navigate('/')}>Back to dashboard</Button>
    </div>
  );
}

export function RequireAuth({ children, perm }: { children: ReactNode; perm?: string }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  if (!user) {
    return (
      <div className="card mx-auto mt-10 max-w-md p-8 text-center">
        <Icon name="user" size={28} className="mx-auto text-nova-300" />
        <p className="mt-3 font-medium text-fg">Sign in to continue</p>
        <p className="muted mt-1 text-sm">This area needs an account.</p>
        <Button variant="primary" className="mt-5" onClick={() => navigate(`/login?next=${encodeURIComponent(pathname)}`)}>Sign in</Button>
      </div>
    );
  }
  if (perm && !can(user, perm)) {
    return (
      <div className="card mx-auto mt-10 max-w-md p-8 text-center">
        <Icon name="shield" size={28} className="mx-auto text-amber-300" />
        <p className="mt-3 font-medium text-fg">You don't have access to this area</p>
        <p className="muted mt-1 text-sm">Ask an administrator for the required role.</p>
      </div>
    );
  }
  return <>{children}</>;
}

export function App() {
  const { pathname } = useLocation();
  if (pathname === '/kiosk') return <><KioskPage /><Toasts /></>;
  if (pathname === '/login' || pathname === '/register') return <><AuthPage mode={pathname === '/login' ? 'login' : 'register'} /><Toasts /></>;
  return (
    <Shell>
      <Routes
        routes={[
          { path: '/', render: () => <DashboardPage /> },
          { path: '/live', render: () => <LivePage /> },
          { path: '/analysis', render: () => <RequireAuth><VideoAnalysisPage /></RequireAuth> },
          { path: '/signs', render: () => <ExplorerPage /> },
          { path: '/signs/:id', render: (p) => <SignDetailPage id={p.id} /> },
          { path: '/communicate', render: () => <CommunicatePage /> },
          { path: '/academy', render: () => <AcademyPage /> },
          { path: '/dataset', render: () => <DatasetLabPage /> },
          { path: '/ai', render: () => <AILabPage /> },
          { path: '/research', render: () => <ResearchPage /> },
          { path: '/viz', render: () => <VizPage /> },
          { path: '/admin', render: () => <RequireAuth perm="admin:users"><AdminPage /></RequireAuth> },
          { path: '/settings', render: () => <RequireAuth><SettingsPage /></RequireAuth> },
        ]}
        fallback={<NotFound />}
      />
      <Toasts />
    </Shell>
  );
}

export const cx = clsx;

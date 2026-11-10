import { useState } from 'react';
import { Button, Card, Empty, ErrorNote, Field, Input, PageHeader, Select, StatusBadge, Table, fmt } from '../components/ui';
import { api } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { auth, prefs, type Theme, toast, type User, useAuth, usePrefs } from '../lib/store';

export function SettingsPage() {
  const { user } = useAuth();
  const p = usePrefs();
  const [name, setName] = useState(user?.display_name ?? '');
  const [pw, setPw] = useState({ current_password: '', new_password: '' });
  const profile = useMutation((b: Record<string, unknown>) => api<User>('/me', { method: 'PATCH', body: b }), { onSuccess: (u) => { auth.setUser(u); toast('Saved'); setPw({ current_password: '', new_password: '' }); } });
  const notes = useQuery<{ id: number; title: string; body: string; read_at: string | null; created_at: string }[]>('/notifications');
  const read = useMutation((id: number) => api(`/notifications/${id}/read`, { method: 'POST' }), { invalidates: ['/notifications'] });
  const history = useQuery<any[]>('/history');
  const bookmarks = useQuery<any[]>('/bookmarks');
  const logoutAll = useMutation(() => api('/auth/logout-all', { method: 'POST' }), { onSuccess: () => { toast('Signed out on every device'); auth.logout(); } });
  const clear = useMutation(() => api('/history', { method: 'DELETE' }), { invalidates: ['/history', '/dashboard'], onSuccess: () => toast('History cleared') });
  const delOne = useMutation((id: number) => api(`/history/${id}`, { method: 'DELETE' }), { invalidates: ['/history'] });

  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Core" title="Settings & activity" />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Profile">
          <div className="space-y-4">
            <ErrorNote error={profile.error} />
            <Field label="Display name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
            <Field label="Preferred meaning language">{(id) => <Select id={id} value={p.language} onChange={(e) => { const l = e.target.value as 'en' | 'hi' | 'kn'; prefs.set({ language: l }); profile.mutate({ preferred_language: l }); }}><option value="en">English</option><option value="hi">हिन्दी</option><option value="kn">ಕನ್ನಡ</option></Select>}</Field>
            <Button variant="primary" loading={profile.pending} onClick={() => profile.mutate({ display_name: name })}>Save profile</Button>
            <div className="border-t border-ink-700 pt-4">
              <p className="label mb-3">Change password</p>
              <div className="space-y-3">
                <Field label="Current password">{(id) => <Input id={id} type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />}</Field>
                <Field label="New password" hint="At least 10 characters.">{(id) => <Input id={id} type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />}</Field>
                <Button disabled={pw.new_password.length < 10} onClick={() => profile.mutate(pw)}>Update password</Button>
              </div>
            </div>
            <div className="border-t border-ink-700 pt-4">
              <p className="label mb-1">Sessions</p>
              <p className="mb-3 text-sm text-ink-400">Signs this account out on every device and browser, including this one.</p>
              <Button variant="ghost" onClick={() => confirm('Sign out on every device?') && logoutAll.mutate(undefined)}>Sign out everywhere</Button>
            </div>
          </div>
        </Card>
        <Card title="Accessibility" subtitle="Stored on this device">
          <div className="space-y-3 text-sm">
            <Field label="Theme">{(id) => <Select id={id} value={p.theme} onChange={(e) => prefs.set({ theme: e.target.value as Theme })}><option value="light">Light</option><option value="dark">Dark</option><option value="system">Match my device</option></Select>}</Field>
            {([['highContrast', 'High contrast'], ['reducedMotion', 'Reduce motion'], ['largeText', 'Larger text']] as const).map(([k, label]) => (
              <label key={k} className="flex items-center justify-between gap-3 rounded-lg border border-ink-700 px-3 py-2.5">
                {label}
                <input type="checkbox" role="switch" className="size-5 accent-nova-500" checked={p[k]} onChange={(e) => prefs.set({ [k]: e.target.checked })} />
              </label>
            ))}
            <Field label={`Speech rate: ${p.speechRate.toFixed(1)}×`}>{(id) => <input id={id} type="range" min={0.5} max={1.5} step={0.1} value={p.speechRate} onChange={(e) => prefs.set({ speechRate: Number(e.target.value) })} className="w-full accent-nova-500" />}</Field>
            <Link to="/kiosk" className="inline-block text-nova-300 hover:underline">Open kiosk mode</Link>
          </div>
        </Card>
        <Card title="Notifications">
          {!notes.data?.length ? <p className="muted text-sm">No notifications.</p> : (
            <ul className="space-y-2 text-sm">{notes.data.map((n) => (
              <li key={n.id} className={`rounded-lg border p-3 ${n.read_at ? 'border-ink-700 opacity-70' : 'border-nova-500/40'}`}>
                <p className="font-medium text-fg">{n.title}</p>{n.body && <p className="muted">{n.body}</p>}
                <p className="mt-1 flex justify-between text-xs text-ink-500">{fmt.date(n.created_at)}{!n.read_at && <button className="text-nova-300 hover:underline" onClick={() => read.mutate(n.id)}>Mark read</button>}</p>
              </li>
            ))}</ul>
          )}
        </Card>
      </div>
      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Recognition history" action={history.data?.length ? <Button size="sm" variant="ghost" icon="trash" onClick={() => confirm('Delete all saved recognition history?') && clear.mutate(undefined)}>Clear all</Button> : undefined}>
          <span id="history" />
          {!history.data?.length ? <Empty icon="camera" title="No saved results" /> : (
            <Table head={['Time', 'State', 'Top prediction', 'Correction', '']}>
              {history.data.map((h) => (
                <tr key={h.id}>
                  <td className="px-3 py-2 text-xs text-ink-400">{fmt.date(h.created_at)}</td>
                  <td className="px-3 py-2"><StatusBadge status={h.state} /></td>
                  <td className="px-3 py-2">{h.top?.[0]?.label ?? '-'}</td>
                  <td className="px-3 py-2 font-mono text-xs">{h.corrected_sign ?? ''}</td>
                  <td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" icon="trash" aria-label="Delete entry" onClick={() => delOne.mutate(h.id)} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Bookmarks">
          {!bookmarks.data?.length ? <p className="muted text-sm">Bookmark signs in the Sign Explorer.</p> : (
            <ul className="space-y-1.5">{bookmarks.data.map((b) => <li key={b.sign_id}><Link to={`/signs/${b.sign_id}`} className="flex justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-ink-800">{b.canonical_sign_name}<StatusBadge status={b.verification_status} /></Link></li>)}</ul>
          )}
        </Card>
      </div>
    </div>
  );
}

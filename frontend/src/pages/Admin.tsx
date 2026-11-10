import { useState } from 'react';
import { Badge, Button, Card, Dialog, ErrorNote, Input, Loading, PageHeader, StatusBadge, Table, Tabs, fmt } from '../components/ui';
import { api, qs } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { toast, useAuth } from '../lib/store';

const ROLES = ['admin', 'linguist', 'data_curator', 'researcher', 'teacher', 'learner'];
type U = { id: number; email: string; display_name: string; roles: string[]; is_active: boolean; created_at: string };

export function AdminPage() {
  const [tab, setTab] = useState<'users' | 'feedback' | 'audit'>('users');
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Admin" title="Administration" actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'users', label: 'Users & roles' }, { id: 'feedback', label: 'Feedback inbox' }, { id: 'audit', label: 'Audit log' }]} />}>
        Roles are enforced server-side on every request. Changes here are written to the audit log.
      </PageHeader>
      {tab === 'users' && <Users />}
      {tab === 'feedback' && <Feedback />}
      {tab === 'audit' && <Audit />}
    </div>
  );
}

function Users() {
  const { user: me } = useAuth();
  const [q, setQ] = useState('');
  const { data, error } = useQuery<U[]>(`/admin/users${qs({ q })}`);
  const [edit, setEdit] = useState<U | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [reset, setReset] = useState<{ email: string; code: string; expires_at: string } | null>(null);
  const issue = useMutation((u: U) => api<{ code: string; expires_at: string }>(`/admin/users/${u.id}/password-reset`, { method: 'POST' }).then((r) => ({ ...r, email: u.email })), { onSuccess: (r) => setReset(r) });
  const save = useMutation((b: { id: number; roles?: string[]; is_active?: boolean }) => api(`/admin/users/${b.id}`, { method: 'PATCH', body: { roles: b.roles, is_active: b.is_active } }), { invalidates: ['/admin'], onSuccess: () => { toast('User updated'); setEdit(null); } });
  return (
    <Card title="Users" action={<Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email or name" aria-label="Search users" className="w-64" />}>
      <ErrorNote error={error ?? save.error ?? issue.error} />
      {reset && (
        <div className="mb-3 rounded-lg border border-nova-500/40 p-3 text-sm" role="status">
          <p>One-time reset code for <strong>{reset.email}</strong> (valid until {fmt.date(reset.expires_at)}). It is shown only once; give it to the user through a trusted channel. They enter it at <code>/reset-password</code>.</p>
          <p className="mt-2 flex items-center gap-2"><code className="break-all rounded bg-ink-900 px-2 py-1" data-testid="reset-code">{reset.code}</code><Button size="sm" variant="ghost" onClick={() => setReset(null)}>Hide</Button></p>
        </div>
      )}
      {!data ? <Loading /> : (
        <Table head={['Name', 'Email', 'Roles', 'Status', 'Created', '']}>
          {data.map((u) => (
            <tr key={u.id}>
              <td className="px-3 py-2">{u.display_name}</td>
              <td className="px-3 py-2 text-ink-300">{u.email}</td>
              <td className="px-3 py-2"><div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} tone={r === 'admin' ? 'nova' : r === 'linguist' ? 'ok' : 'neutral'}>{r}</Badge>)}</div></td>
              <td className="px-3 py-2">{u.is_active ? <Badge tone="ok">active</Badge> : <Badge tone="bad">disabled</Badge>}</td>
              <td className="px-3 py-2 text-xs text-ink-400">{fmt.date(u.created_at)}</td>
              <td className="px-3 py-2 text-right"><div className="flex justify-end gap-1">
                <Button size="sm" onClick={() => { setEdit(u); setRoles(u.roles); }}>Roles</Button>
                {u.id !== me?.id && <Button size="sm" variant="ghost" onClick={() => issue.mutate(u)}>Reset code</Button>}
                {u.id !== me?.id && <Button size="sm" variant="ghost" onClick={() => save.mutate({ id: u.id, is_active: !u.is_active })}>{u.is_active ? 'Disable' : 'Enable'}</Button>}
              </div></td>
            </tr>
          ))}
        </Table>
      )}
      <Dialog open={!!edit} onClose={() => setEdit(null)} title={`Roles · ${edit?.display_name ?? ''}`}
        footer={<><Button variant="ghost" onClick={() => setEdit(null)}>Cancel</Button><Button variant="primary" loading={save.pending} onClick={() => edit && save.mutate({ id: edit.id, roles })}>Save</Button></>}>
        <fieldset className="space-y-2 text-sm"><legend className="sr-only">Roles</legend>
          {ROLES.map((r) => <label key={r} className="flex items-center gap-2"><input type="checkbox" className="accent-nova-500" checked={roles.includes(r)} onChange={(e) => setRoles(e.target.checked ? [...roles, r] : roles.filter((x) => x !== r))} />{r}{r === 'linguist' && <span className="muted text-xs">· only for qualified ISL reviewers</span>}</label>)}
        </fieldset>
      </Dialog>
    </Card>
  );
}

function Feedback() {
  const { data } = useQuery<any[]>('/feedback');
  const upd = useMutation((b: { id: number; status: string }) => api(`/feedback/${b.id}`, { method: 'PATCH', body: { status: b.status } }), { invalidates: ['/feedback'] });
  if (!data) return <Loading />;
  return (
    <Card title="Feedback inbox">
      <Table head={['Kind', 'Sign', 'Message', 'From', 'Status', '']}>
        {data.map((f) => (
          <tr key={f.id}>
            <td className="px-3 py-2"><Badge>{f.kind}</Badge></td>
            <td className="px-3 py-2 font-mono text-xs">{f.sign_id ?? '-'}</td>
            <td className="max-w-md px-3 py-2 text-ink-200">{f.message}</td>
            <td className="px-3 py-2 text-xs text-ink-400">{f.author ?? 'anonymous'}<br />{fmt.date(f.created_at)}</td>
            <td className="px-3 py-2"><StatusBadge status={f.status} /></td>
            <td className="px-3 py-2 text-right">{f.status === 'open' && <div className="flex justify-end gap-1"><Button size="sm" onClick={() => upd.mutate({ id: f.id, status: 'resolved' })}>Resolve</Button><Button size="sm" variant="ghost" onClick={() => upd.mutate({ id: f.id, status: 'dismissed' })}>Dismiss</Button></div>}</td>
          </tr>
        ))}
      </Table>
    </Card>
  );
}

function Audit() {
  const [action, setAction] = useState('');
  const { data } = useQuery<any[]>(`/admin/audit${qs({ action, limit: 200 })}`);
  return (
    <Card title="Audit log" action={<Input value={action} onChange={(e) => setAction(e.target.value)} placeholder="Filter action prefix, e.g. consent" aria-label="Filter audit actions" className="w-72" />}>
      {!data ? <Loading /> : (
        <Table head={['Time', 'Actor', 'Action', 'Target', 'Detail']} className="max-h-[600px]">
          {data.map((a) => (
            <tr key={a.id}>
              <td className="whitespace-nowrap px-3 py-2 text-xs text-ink-400">{fmt.date(a.created_at)}</td>
              <td className="px-3 py-2 text-xs">{a.actor ?? '-'}</td>
              <td className="px-3 py-2"><code className="text-xs text-nova-300">{a.action}</code></td>
              <td className="px-3 py-2 font-mono text-xs">{a.target ?? ''}</td>
              <td className="max-w-sm truncate px-3 py-2 text-xs text-ink-400">{a.detail ? JSON.stringify(a.detail) : ''}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

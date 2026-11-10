import { useState } from 'react';
import { Badge, Button, Card, Empty, ErrorNote, Field, Input, Loading, Notice, PageHeader, Table, fmt } from '../components/ui';
import { useT } from '../i18n';
import { api } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { toast } from '../lib/store';

type Teaching = { id: number; name: string; join_code: string; members: number; created_at: string };
type Joined = { id: number; name: string; teacher: string; joined_at: string };
type Mine = { teaching: Teaching[]; joined: Joined[]; can_teach: boolean };
type Learner = { user_id: number; name: string; attempts: number; accuracy: number | null; signs_practised: number;
  current_streak: number; last_active: string | null; hardest: string[] };
type Progress = { class: Teaching; learners: Learner[]; hard_signs: { sign_id: string; name: string; attempts: number; accuracy: number }[]; note: string };

export function ClassesPage() {
  const t = useT();
  const { data, error, refetch } = useQuery<Mine>('/classes');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [open, setOpen] = useState<number | null>(null);
  const create = useMutation((n: string) => api('/classes', { body: { name: n } }), { invalidates: ['/classes'], onSuccess: () => { setName(''); toast(t('Class created')); } });
  const join = useMutation((c: string) => api('/classes/join', { body: { code: c } }), { invalidates: ['/classes'], onSuccess: () => { setCode(''); toast(t('Joined the class')); } });
  const leave = useMutation((id: number) => api(`/classes/${id}/membership`, { method: 'DELETE' }), { invalidates: ['/classes'], onSuccess: () => toast(t('You left the class')) });
  const del = useMutation((id: number) => api(`/classes/${id}`, { method: 'DELETE' }), { invalidates: ['/classes'], onSuccess: () => { setOpen(null); refetch(); } });
  if (!data) return <><PageHeader title="Classes" /><ErrorNote error={error} />{!error && <Loading />}</>;
  return (
    <>
      <PageHeader title="Classes">{t('Teachers follow their learners’ practice; learners join with a code and can leave at any time.')}</PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Join a class">
          <ErrorNote error={join.error} />
          <Notice tone="info" title="Privacy">{t('Joining shares a summary of your quiz and Practice Coach attempts with the teacher. Your recognition history and recordings are never shared.')}</Notice>
          <div className="mt-3 flex items-end gap-2">
            <div className="flex-1"><Field label="Class code">{(id) => <Input id={id} value={code} maxLength={16} onChange={(e) => setCode(e.target.value.toUpperCase())} />}</Field></div>
            <Button disabled={code.trim().length < 4} loading={join.pending} onClick={() => join.mutate(code.trim())}>Join</Button>
          </div>
          {data.joined.length > 0 && (
            <ul className="mt-4 space-y-2">{data.joined.map((j) => (
              <li key={j.id} className="flex items-center justify-between rounded-lg border border-ink-700 px-3 py-2 text-sm">
                <span><span className="font-medium text-fg">{j.name}</span> <span className="text-ink-400">· {j.teacher}</span></span>
                <Button size="sm" variant="ghost" onClick={() => leave.mutate(j.id)}>Leave</Button>
              </li>))}
            </ul>
          )}
        </Card>
        {data.can_teach ? (
          <Card title="My classes" subtitle="Share the code with your learners">
            <ErrorNote error={create.error} />
            <div className="flex items-end gap-2">
              <div className="flex-1"><Field label="New class name">{(id) => <Input id={id} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />}</Field></div>
              <Button variant="primary" disabled={!name.trim()} loading={create.pending} onClick={() => create.mutate(name.trim())}>Create class</Button>
            </div>
            {!data.teaching.length ? <p className="muted mt-4 text-sm">{t('No classes yet.')}</p> : (
              <ul className="mt-4 space-y-2">{data.teaching.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ink-700 px-3 py-2 text-sm">
                  <span><span className="font-medium text-fg">{c.name}</span> <span className="text-ink-400">· {c.members} {t('learners')}</span></span>
                  <span className="flex items-center gap-2"><code className="rounded bg-ink-900 px-2 py-0.5" data-testid="class-code">{c.join_code}</code>
                    <Button size="sm" onClick={() => setOpen(c.id)}>{t('Open')}</Button></span>
                </li>))}
              </ul>
            )}
          </Card>
        ) : (
          <Card title="Teaching"><Empty icon="cap" title="Ask an administrator for the teacher role to create classes" /></Card>
        )}
      </div>
      {open !== null && <ClassProgress id={open} onDelete={() => confirm(t('Delete this class?')) && del.mutate(open)} />}
    </>
  );
}

function ClassProgress({ id, onDelete }: { id: number; onDelete: () => void }) {
  const t = useT();
  const { data, error } = useQuery<Progress>(`/classes/${id}/progress`);
  if (!data) return <div className="mt-4"><ErrorNote error={error} />{!error && <Loading />}</div>;
  const pct = (x: number | null) => (x === null ? '–' : `${Math.round(x * 100)}%`);
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-3">
      <Card className="xl:col-span-2" title={`${data.class.name} · ${t('Teacher dashboard')}`} subtitle={data.note}
        action={<Button size="sm" variant="ghost" icon="trash" onClick={onDelete}>Delete class</Button>}>
        {!data.learners.length ? <Empty icon="user" title="No learners have joined yet" /> : (
          <Table head={['Learner', 'Attempts', 'Accuracy', 'Signs practised', 'Streak', 'Last active', 'Hardest signs']}>
            {data.learners.map((l) => (
              <tr key={l.user_id}>
                <td className="px-3 py-2 font-medium text-fg">{l.name}</td>
                <td className="px-3 py-2">{l.attempts}</td>
                <td className="px-3 py-2">{pct(l.accuracy)}</td>
                <td className="px-3 py-2">{l.signs_practised}</td>
                <td className="px-3 py-2">{l.current_streak}</td>
                <td className="px-3 py-2 text-xs text-ink-400">{l.last_active ? fmt.date(l.last_active) : '–'}</td>
                <td className="px-3 py-2"><div className="flex flex-wrap gap-1">{l.hardest.map((s) => <Link key={s} to={`/signs/${s}`}><Badge>{s}</Badge></Link>)}</div></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Card title="Hard signs for this class" subtitle="Lowest accuracy, at least 3 attempts">
        {!data.hard_signs.length ? <p className="muted text-sm">{t('Not enough attempts yet.')}</p> : (
          <ul className="space-y-2 text-sm">{data.hard_signs.map((h) => (
            <li key={h.sign_id} className="flex justify-between"><Link to={`/practice?sign=${h.sign_id}`} className="hover:text-nova-300">{h.name}</Link>
              <span className="text-ink-400">{pct(h.accuracy)} · {h.attempts}</span></li>))}
          </ul>
        )}
      </Card>
    </div>
  );
}

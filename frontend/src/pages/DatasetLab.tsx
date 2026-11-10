import { useCallback, useRef, useState } from 'react';
import { RequireAuth } from '../App';
import { CameraStage } from '../components/CameraStage';
import { HBars } from '../components/charts';
import { Badge, Button, Card, Dialog, Empty, ErrorNote, Field, Input, Loading, Meter, Notice, PageHeader, Select, Stat, StatusBadge, Table, Tabs, fmt } from '../components/ui';
import { api, API, qs } from '../lib/api';
import type { Frame } from '../lib/features';
import { useMutation, useQuery } from '../lib/query';
import { auth, can, toast, useAuth } from '../lib/store';
import type { DatasetStats, SignSummary } from '../lib/types';

type Tab = 'overview' | 'signers' | 'studio' | 'review' | 'versions';
type Signer = { id: number; signer_code: string; dominant_hand: string | null; age_band: string | null; region: string | null; sessions: number; recordings: number; consent: null | { id: number; scopes: string[]; granted_at: string; retention_until: string | null; expired?: boolean } };
type Session = { id: number; session_code: string; signer_id: number; signer_code: string; environment: Record<string, string>; created_at: string };
type Rec = { id: number; recording_code: string; sign_id: string; status: string; duration_s: number; width: number; height: number; size_bytes: number; quality: any; created_at: string; session_code: string; signer_code: string; has_landmarks: boolean };
type Row = { sign_id: string; canonical_sign_name: string; category: string; verification_status: string; data_readiness: string; external_videos: number; approved: number; pending: number; signers: number; sessions: number };

export function DatasetLabPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('overview');
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Dataset Intelligence Lab" title="Dataset Lab"
        actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'overview', label: 'Overview' }, { id: 'signers', label: 'Signers & consent' }, { id: 'studio', label: 'Recording Studio' }, { id: 'review', label: 'Review queue' }, { id: 'versions', label: 'Versions & validation' }]} />}>
        Consent-first collection of authentic ISL recordings. Counts below are separate on purpose: a class slot is not a verified sign, and a verified sign is not training data.
      </PageHeader>
      {tab === 'overview' && <Overview />}
      {tab !== 'overview' && (
        <RequireAuth perm="dataset:read">
          {tab === 'signers' && <Signers canWrite={can(user, 'dataset:write')} />}
          {tab === 'studio' && (can(user, 'dataset:write') ? <Studio /> : <Notice title="Recording requires the data curator role" />)}
          {tab === 'review' && <Review />}
          {tab === 'versions' && <Versions />}
        </RequireAuth>
      )}
    </div>
  );
}

function Overview() {
  const { user } = useAuth();
  const { data: s, error } = useQuery<DatasetStats>('/dataset/stats');
  const rows = useQuery<Row[]>(can(user, 'dataset:read') ? '/dataset/signs' : null);
  const [filter, setFilter] = useState('');
  if (error) return <ErrorNote error={error} />;
  if (!s) return <Loading rows={4} />;
  const shown = rows.data?.filter((r) => !filter || r.data_readiness === filter) ?? [];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Class slots" value={s.class_slots} icon="layers" tone="nova" />
        <Stat label="Verified vocabulary" value={s.verified_classes} icon="check" tone="ok" sub={`${s.review_pending_classes} pending review`} />
        <Stat label="Classes w/ recordings" value={s.classes_with_recordings} icon="record" tone="signal" />
        <Stat label="Approved for training" value={s.classes_approved_for_training} icon="rocket" tone="warn" />
        <Stat label="Approved samples" value={s.approved_samples} icon="database" sub={`${s.recordings.pending_review ?? 0} awaiting review`} />
        <Stat label="Signers" value={s.signers} icon="user" sub={`pseudonymous · ${s.sessions} sessions`} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Readiness funnel" subtitle="How many of the 200 classes reach each stage">
          <div className="space-y-3">
            <Meter label="Reference found (licensed external source)" value={s.reference_found_classes + s.verified_classes + s.review_pending_classes} max={s.class_slots} tone="signal" />
            <Meter label="Linguistically verified" value={s.verified_classes} max={s.class_slots} tone="ok" />
            <Meter label="Have local recordings" value={s.classes_with_recordings} max={s.class_slots} tone="nova" />
            <Meter label="Approved for training" value={s.classes_approved_for_training} max={s.class_slots} tone="warn" />
          </div>
          <p className="muted mt-4 text-xs">Training approval needs a verified sign, ≥{s.thresholds.min_approved_samples} approved recordings and ≥{s.thresholds.min_signers} distinct signers.</p>
        </Card>
        <Card title="Verified translations">
          <HBars label="Verified meanings per language" max={s.class_slots} data={[{ label: 'English', value: s.verified_translations.en }, { label: 'Hindi', value: s.verified_translations.hi }, { label: 'Kannada', value: s.verified_translations.kn }]} />
          <p className="muted mt-4 text-xs">Hindi and Kannada meanings are intentionally blank until a bilingual reviewer enters them.</p>
        </Card>
        <Card title="External source">
          <p className="text-sm text-ink-200">{s.external_source.name}</p>
          <p className="mt-1 font-display text-3xl font-semibold text-fg">{s.external_source.videos_listed.toLocaleString()}</p>
          <p className="muted text-xs">videos listed in the official train/val/test split for these 200 classes</p>
          <div className="mt-3"><Badge tone={s.external_source.downloaded ? 'ok' : 'warn'}>{s.external_source.downloaded ? 'Imported' : 'Not downloaded in this deployment'}</Badge></div>
          <p className="muted mt-3 text-xs">See docs/DATASET_PROTOCOL.md for the import command (56.8 GB from Zenodo).</p>
        </Card>
      </div>
      {can(user, 'dataset:read') && (
        <Card title="Per-class readiness" action={
          <Select aria-label="Filter readiness" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-9 w-auto max-w-full py-0">
            <option value="">All readiness states</option>
            {Object.keys(s.readiness).map((k) => <option key={k} value={k}>{k.replaceAll('_', ' ')} ({s.readiness[k]})</option>)}
          </Select>}>
          {rows.loading ? <Loading /> : (
            <Table head={['ID', 'Sign', 'Verification', 'Readiness', 'Approved', 'Pending', 'Signers', 'External']} className="max-h-[520px]" scrollLabel="Per-sign readiness table">
              {shown.map((r) => (
                <tr key={r.sign_id}>
                  <td className="px-3 py-2 font-mono text-xs text-ink-400">{r.sign_id}</td>
                  <td className="px-3 py-2">{r.canonical_sign_name}</td>
                  <td className="px-3 py-2"><StatusBadge status={r.verification_status} /></td>
                  <td className="px-3 py-2"><StatusBadge status={r.data_readiness} /></td>
                  <td className="px-3 py-2 tabular-nums">{r.approved}</td>
                  <td className="px-3 py-2 tabular-nums">{r.pending}</td>
                  <td className="px-3 py-2 tabular-nums">{r.signers}</td>
                  <td className="px-3 py-2 tabular-nums text-ink-400">{r.external_videos}</td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

const SCOPES = [
  ['recording_storage', 'Store my recordings securely (required)'],
  ['model_training', 'Use my recordings to train recognition models'],
  ['research_display', 'Show my recordings to approved reviewers and researchers'],
  ['public_reference_media', 'Publish my recordings as public reference media'],
] as const;

function Signers({ canWrite }: { canWrite: boolean }) {
  const { data, loading } = useQuery<Signer[]>('/dataset/signers');
  const [creating, setCreating] = useState(false);
  const [consentFor, setConsentFor] = useState<Signer | null>(null);
  const [form, setForm] = useState({ dominant_hand: '', age_band: '', region: '', deaf_status: '' });
  const [scopes, setScopes] = useState<string[]>(['recording_storage']);
  const [confirmed, setConfirmed] = useState(false);
  const [retention, setRetention] = useState('');
  const inv = ['/dataset', '/dashboard'];
  const create = useMutation((b: typeof form) => api('/dataset/signers', { body: Object.fromEntries(Object.entries(b).filter(([, v]) => v)) }), { invalidates: inv, onSuccess: (s: Signer) => { toast(`Registered ${s.signer_code}`); setCreating(false); setConsentFor(s); } });
  const consent = useMutation((s: Signer) => api(`/dataset/signers/${s.id}/consents`, { body: { scopes, confirmed_by_signer: confirmed, retention_until: retention || null } }), { invalidates: inv, onSuccess: () => { toast('Consent recorded'); setConsentFor(null); setConfirmed(false); } });
  const revoke = useMutation((cid: number) => api(`/dataset/consents/${cid}/revoke`, { body: { reason: 'Withdrawn at signer request' } }), { invalidates: inv, onSuccess: (r: { recordings_erased: number }) => toast(`Consent withdrawn; ${r.recordings_erased} recording(s) erased`) });
  const erase = useMutation((id: number) => api(`/dataset/signers/${id}`, { method: 'DELETE' }), { invalidates: inv, onSuccess: () => toast('Signer and media erased') });

  return (
    <Card title="Pseudonymous signers" subtitle="No names, contact details or faces are stored as metadata. Signers are identified by a random code."
      action={canWrite && <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>Register signer</Button>}>
      {loading && !data ? <Loading /> : !data?.length ? <Empty icon="user" title="No signers yet">Register a signer and record their informed consent before recording.</Empty> : (
        <Table head={['Code', 'Profile', 'Consent', 'Sessions', 'Recordings', '']}>
          {data.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2 font-mono text-xs">{s.signer_code}</td>
              <td className="px-3 py-2 text-xs text-ink-300">{[s.dominant_hand && `${s.dominant_hand}-handed`, s.age_band, s.region].filter(Boolean).join(' · ') || '-'}</td>
              <td className="px-3 py-2">{s.consent ? <div className="flex flex-wrap gap-1">{s.consent.scopes.map((x) => <Badge key={x} tone={s.consent!.expired ? 'bad' : 'ok'}>{x.replaceAll('_', ' ')}</Badge>)}</div> : <Badge tone="warn">No consent</Badge>}</td>
              <td className="px-3 py-2 tabular-nums">{s.sessions}</td>
              <td className="px-3 py-2 tabular-nums">{s.recordings}</td>
              <td className="px-3 py-2 text-right">{canWrite && <div className="flex justify-end gap-1">
                {!s.consent && <Button size="sm" onClick={() => setConsentFor(s)}>Record consent</Button>}
                {s.consent && <Button size="sm" variant="ghost" onClick={() => confirm(`Withdraw consent for ${s.signer_code}? Their recordings will be erased.`) && revoke.mutate(s.consent!.id)}>Withdraw</Button>}
                <Button size="sm" variant="ghost" icon="trash" aria-label={`Erase ${s.signer_code}`} onClick={() => confirm(`Erase ${s.signer_code} and all media permanently?`) && erase.mutate(s.id)} />
              </div>}</td>
            </tr>
          ))}
        </Table>
      )}
      <Dialog open={creating} onClose={() => setCreating(false)} title="Register a pseudonymous signer"
        footer={<><Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button><Button variant="primary" loading={create.pending} onClick={() => create.mutate(form)}>Register</Button></>}>
        <div className="grid gap-4 md:grid-cols-2">
          <ErrorNote error={create.error} />
          <Field label="Dominant hand">{(id) => <Select id={id} value={form.dominant_hand} onChange={(e) => setForm({ ...form, dominant_hand: e.target.value })}><option value="">Prefer not to say</option><option value="right">Right</option><option value="left">Left</option><option value="both">Both</option></Select>}</Field>
          <Field label="Age band">{(id) => <Select id={id} value={form.age_band} onChange={(e) => setForm({ ...form, age_band: e.target.value })}><option value="">Prefer not to say</option>{['18-25', '26-35', '36-50', '51-65', '65+'].map((a) => <option key={a}>{a}</option>)}</Select>}</Field>
          <Field label="Region" hint="Broad region for dialect analysis, e.g. 'Karnataka'.">{(id) => <Input id={id} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />}</Field>
          <Field label="Hearing status">{(id) => <Select id={id} value={form.deaf_status} onChange={(e) => setForm({ ...form, deaf_status: e.target.value })}><option value="">Prefer not to say</option><option value="deaf">Deaf</option><option value="hard_of_hearing">Hard of hearing</option><option value="hearing">Hearing</option><option value="coda">CODA</option></Select>}</Field>
        </div>
      </Dialog>
      <Dialog open={!!consentFor} onClose={() => setConsentFor(null)} title={`Informed consent · ${consentFor?.signer_code ?? ''}`}
        footer={<><Button variant="ghost" onClick={() => setConsentFor(null)}>Cancel</Button><Button variant="primary" disabled={!confirmed} loading={consent.pending} onClick={() => consentFor && consent.mutate(consentFor)}>Record consent</Button></>}>
        <div className="space-y-4 text-sm">
          <ErrorNote error={consent.error} />
          <Notice title="Consent text v1 (isl-nova-consent-v1)">Explain each purpose to the signer in ISL, check they understand, and record only the purposes they agree to. Consent can be withdrawn at any time; withdrawal erases their recordings.</Notice>
          <fieldset className="space-y-2"><legend className="label mb-1">Permitted purposes</legend>
            {SCOPES.map(([k, label]) => (
              <label key={k} className="flex items-start gap-2"><input type="checkbox" className="mt-1 accent-nova-500" checked={scopes.includes(k)} disabled={k === 'recording_storage'} onChange={(e) => setScopes(e.target.checked ? [...scopes, k] : scopes.filter((x) => x !== k))} />{label}</label>
            ))}
          </fieldset>
          <Field label="Retain until (optional)" hint="Recordings must be deleted after this date.">{(id) => <Input id={id} type="date" value={retention} onChange={(e) => setRetention(e.target.value)} />}</Field>
          <label className="flex items-start gap-2 rounded-lg border border-ink-600 p-3"><input type="checkbox" className="mt-1 accent-nova-500" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />The signer has explicitly confirmed this consent.</label>
        </div>
      </Dialog>
    </Card>
  );
}

function Studio() {
  const signers = useQuery<Signer[]>('/dataset/signers');
  const sessions = useQuery<Session[]>('/dataset/sessions');
  const [signerId, setSignerId] = useState<number | ''>('');
  const [sessionId, setSessionId] = useState<number | ''>('');
  const [env, setEnv] = useState({ lighting: 'indoor-even', background: 'plain', camera_distance: 'medium' });
  const [q, setQ] = useState('');
  const [sign, setSign] = useState<SignSummary | null>(null);
  const signs = useQuery<{ items: SignSummary[] }>(q ? `/signs${qs({ q, size: 6 })}` : null);
  const stream = useRef<MediaStream | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const lm = useRef<{ frames: Frame[]; aspect: number } | null>(null);
  const [phase, setPhase] = useState<'idle' | 'countdown' | 'recording' | 'review'>('idle');
  const [count, setCount] = useState(0);
  const [clip, setClip] = useState<{ blob: Blob; url: string; frames: Frame[]; aspect: number } | null>(null);
  const onFrame = useCallback((f: Frame, a: number) => { if (lm.current) { lm.current.frames.push(f); lm.current.aspect = a; } }, []);
  const consented = signers.data?.filter((s) => s.consent && !s.consent.expired) ?? [];
  const mySessions = sessions.data?.filter((s) => s.signer_id === signerId) ?? [];

  const newSession = useMutation(() => api<Session>('/dataset/sessions', { body: { signer_id: signerId, ...env } }), { invalidates: ['/dataset/sessions'], onSuccess: (s) => { setSessionId(s.id); toast(`Session ${s.session_code} opened`); } });
  const upload = useMutation(async () => {
    const fd = new FormData();
    fd.append('sign_id', sign!.sign_id);
    fd.append('session_id', String(sessionId));
    fd.append('file', new File([clip!.blob], `${sign!.sign_id}.webm`, { type: clip!.blob.type || 'video/webm' }));
    fd.append('landmarks', JSON.stringify({ aspect: clip!.aspect, frames: clip!.frames }));
    return api<Rec>('/dataset/recordings', { form: fd });
  }, { invalidates: ['/dataset', '/dashboard', '/signs'], onSuccess: (r) => { toast(`Uploaded ${r.recording_code}; awaiting review`); discard(); } });

  const start = () => {
    if (!stream.current) return;
    setPhase('countdown');
    let n = 3;
    setCount(n);
    const t = setInterval(() => {
      n -= 1; setCount(n);
      if (n > 0) return;
      clearInterval(t);
      chunks.current = [];
      lm.current = { frames: [], aspect: 4 / 3 };
      const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
      const r = new MediaRecorder(stream.current!, { mimeType: mime, videoBitsPerSecond: 2_500_000 });
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.onstop = () => {
        const blob = new Blob(chunks.current, { type: 'video/webm' });
        const l = lm.current ?? { frames: [], aspect: 4 / 3 };
        lm.current = null;
        setClip({ blob, url: URL.createObjectURL(blob), frames: l.frames, aspect: l.aspect });
        setPhase('review');
      };
      rec.current = r;
      r.start();
      setPhase('recording');
      setTimeout(() => r.state === 'recording' && r.stop(), 2500);
    }, 800);
  };
  const discard = () => { if (clip) URL.revokeObjectURL(clip.url); setClip(null); setPhase('idle'); };
  const handRatio = clip ? clip.frames.filter((f) => f.left || f.right).length / Math.max(1, clip.frames.length) : 0;
  const ready = signerId && sessionId && sign;

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div className="space-y-4">
        <Card title="1 · Signer & session">
          {!consented.length ? <Notice tone="warn" title="No signer with active consent">Register a signer and record consent in the Signers tab first.</Notice> : (
            <div className="space-y-3">
              <Field label="Signer">{(id) => <Select id={id} value={signerId} onChange={(e) => { setSignerId(Number(e.target.value) || ''); setSessionId(''); }}><option value="">Choose…</option>{consented.map((s) => <option key={s.id} value={s.id}>{s.signer_code} ({s.consent!.scopes.length} scopes)</option>)}</Select>}</Field>
              {signerId && (
                <>
                  <Field label="Session">{(id) => <Select id={id} value={sessionId} onChange={(e) => setSessionId(Number(e.target.value) || '')}><option value="">New session…</option>{mySessions.map((s) => <option key={s.id} value={s.id}>{s.session_code} · {Object.values(s.environment ?? {}).join(', ')}</option>)}</Select>}</Field>
                  {!sessionId && (
                    <div className="grid grid-cols-3 gap-2">
                      {(['lighting', 'background', 'camera_distance'] as const).map((k) => <Field key={k} label={k.replace('_', ' ')}>{(id) => <Input id={id} value={env[k]} onChange={(e) => setEnv({ ...env, [k]: e.target.value })} />}</Field>)}
                      <Button className="col-span-3" onClick={() => newSession.mutate(undefined)} loading={newSession.pending}>Open session</Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </Card>
        <Card title="2 · Sign to record">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search vocabulary…" aria-label="Search sign to record" />
          <ul className="mt-2 space-y-1">{signs.data?.items.map((s) => <li key={s.sign_id}><button onClick={() => { setSign(s); setQ(''); }} className="flex w-full justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-ink-700">{s.canonical_sign_name}<span className="font-mono text-xs text-ink-500">{s.sign_id}</span></button></li>)}</ul>
          {sign && <div className="mt-3 flex items-center justify-between rounded-xl border border-nova-500/40 bg-nova-500/5 p-3"><div><p className="font-mono text-xs text-ink-400">{sign.sign_id}</p><p className="font-display text-xl font-semibold text-fg">{sign.canonical_sign_name}</p></div><StatusBadge status={sign.verification_status} /></div>}
        </Card>
        <Card title="Recording guidance">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-300">
            <li>Upper body and both hands fully in frame; plain background.</li>
            <li>Start and end with hands resting; sign once at natural speed.</li>
            <li>Vary lighting, distance and speed across sessions, not within a clip.</li>
            <li>Discard any clip where the signer is unhappy with it.</li>
          </ul>
        </Card>
      </div>
      <Card title="3 · Record" subtitle="2.5-second clip after a 3-second countdown. Landmarks are captured alongside the video.">
        <div className="relative">
          <CameraStage onFrame={onFrame} recordStream={(s) => { stream.current = s; }} />
          {phase === 'countdown' && <div className="pointer-events-none absolute inset-0 grid place-items-center"><span className="font-display text-8xl font-semibold text-white">{count}</span></div>}
          {phase === 'recording' && <div className="absolute right-3 top-3"><Badge tone="bad"><span className="live-dot size-2 rounded-full bg-rose-400" />REC</Badge></div>}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="primary" icon="record" disabled={!ready || phase !== 'idle'} onClick={start}>Record clip</Button>
          {!ready && <span className="muted self-center text-sm">Choose a signer, session and sign first.</span>}
        </div>
        {clip && (
          <div className="mt-5 space-y-3 rounded-xl border border-ink-700 p-4">
            <video src={clip.url} controls className="w-full -scale-x-100 rounded-lg" aria-label="Recorded clip preview" />
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge tone={clip.frames.length >= 8 ? 'ok' : 'bad'}>{clip.frames.length} landmark frames</Badge>
              <Badge tone={handRatio >= 0.25 ? 'ok' : 'bad'}>hands in {Math.round(handRatio * 100)}% of frames</Badge>
              <Badge>{fmt.bytes(clip.blob.size)}</Badge>
            </div>
            {handRatio < 0.25 && <Notice tone="warn" title="Hands were rarely detected">The server will accept the video but flag the landmarks as insufficient. Consider re-recording.</Notice>}
            <ErrorNote error={upload.error} />
            <div className="flex gap-2"><Button variant="primary" icon="upload" loading={upload.pending} onClick={() => upload.mutate(undefined)}>Upload for review</Button><Button variant="ghost" icon="trash" onClick={discard}>Discard</Button></div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Review() {
  const { user } = useAuth();
  const [status, setStatus] = useState('pending_review');
  const list = useQuery<Rec[]>(`/dataset/recordings${qs({ status, limit: 100 })}`);
  const [sel, setSel] = useState<Rec | null>(null);
  const [media, setMedia] = useState<string | null>(null);
  const annotate = useMutation(async (decision: string) => {
    const a = await api<{ id: number }>('/annotations', { body: { recording_id: sel!.id, label_sign_id: sel!.sign_id } });
    return decision === 'annotate' ? a : api(`/annotations/${a.id}`, { method: 'PATCH', body: { decision } });
  }, { invalidates: ['/dataset', '/annotations', '/signs', '/dashboard'], onSuccess: () => { toast('Saved'); setSel(null); } });
  const queue = useQuery<any[]>('/annotations?decision=pending');
  const decide = useMutation((b: { id: number; decision: string }) => api(`/annotations/${b.id}`, { method: 'PATCH', body: { decision: b.decision } }), { invalidates: ['/dataset', '/annotations', '/signs', '/dashboard'], onSuccess: () => toast('Review recorded') });
  const del = useMutation((id: number) => api(`/dataset/recordings/${id}`, { method: 'DELETE' }), { invalidates: ['/dataset', '/dashboard'], onSuccess: () => toast('Recording deleted') });

  const open = async (r: Rec) => {
    setSel(r);
    setMedia(null);
    if (can(user, 'dataset:review')) {
      const res = await fetch(`${API}/dataset/recordings/${r.id}/media`, { headers: { Authorization: `Bearer ${auth.get().token}` } });
      if (res.ok) setMedia(URL.createObjectURL(await res.blob()));
    }
  };

  return (
    <div className="space-y-5">
      <Card title="Annotations awaiting a second reviewer" subtitle="Four-eyes rule: an annotation cannot be approved by the person who made it">
        {!queue.data?.length ? <p className="muted text-sm">Nothing waiting.</p> : (
          <Table head={['Recording', 'Label', 'Annotator', '']}>
            {queue.data.map((a) => (
              <tr key={a.id}>
                <td className="px-3 py-2 font-mono text-xs">{a.recording_code}</td>
                <td className="px-3 py-2">{a.label_sign_id} {a.label_sign_id !== a.recording_sign_id && <Badge tone="bad">differs from requested {a.recording_sign_id}</Badge>}</td>
                <td className="px-3 py-2 text-ink-300">{a.annotator}</td>
                <td className="px-3 py-2 text-right">{can(user, 'dataset:review') && <div className="flex justify-end gap-1"><Button size="sm" variant="primary" onClick={() => decide.mutate({ id: a.id, decision: 'approved' })}>Approve</Button><Button size="sm" variant="ghost" onClick={() => decide.mutate({ id: a.id, decision: 'rejected' })}>Reject</Button></div>}</td>
              </tr>
            ))}
          </Table>
        )}
        <ErrorNote error={decide.error} />
      </Card>
      <Card title="Recordings" action={<Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 w-auto py-0">{['pending_review', 'approved', 'rejected', 'deleted'].map((s) => <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>)}</Select>}>
        {list.loading && !list.data ? <Loading /> : !list.data?.length ? <Empty icon="record" title="No recordings in this state" /> : (
          <Table head={['Code', 'Sign', 'Signer', 'Quality', 'Landmarks', 'Created', '']}>
            {list.data.map((r) => (
              <tr key={r.id}>
                <td className="px-3 py-2 font-mono text-xs">{r.recording_code}</td>
                <td className="px-3 py-2">{r.sign_id}</td>
                <td className="px-3 py-2 font-mono text-xs text-ink-400">{r.signer_code}</td>
                <td className="px-3 py-2">{r.quality?.passed ? <Badge tone="ok">passed</Badge> : <Badge tone="warn" >{r.quality?.issues?.length ?? 0} issue(s)</Badge>}</td>
                <td className="px-3 py-2">{r.has_landmarks ? <StatusBadge status={r.quality?.landmarks?.status === 'ok' ? 'succeeded' : 'insufficient_input'} /> : <Badge>none</Badge>}</td>
                <td className="px-3 py-2 text-xs text-ink-400">{fmt.date(r.created_at)}</td>
                <td className="px-3 py-2 text-right"><Button size="sm" onClick={() => open(r)}>Open</Button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Dialog open={!!sel} onClose={() => { setSel(null); if (media) URL.revokeObjectURL(media); }} title={sel?.recording_code ?? ''} wide
        footer={sel && sel.status === 'pending_review' && <>
          <Button variant="ghost" icon="trash" onClick={() => { del.mutate(sel.id); setSel(null); }}>Delete</Button>
          <Button onClick={() => annotate.mutate('annotate')} loading={annotate.pending}>Annotate as {sel.sign_id}</Button>
        </>}>
        {sel && (
          <div className="space-y-3 text-sm">
            <ErrorNote error={annotate.error} />
            {media ? <video src={media} controls className="w-full rounded-lg" /> : <Notice title="Media playback requires the linguist or admin role">Reviewers with permission see the clip here; access is audited.</Notice>}
            <dl className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {[['Sign', sel.sign_id], ['Duration', `${sel.duration_s}s`], ['Resolution', `${sel.width}×${sel.height}`], ['Size', fmt.bytes(sel.size_bytes)]].map(([k, v]) => <div key={k} className="rounded-lg bg-ink-800 p-2"><dt className="label">{k}</dt><dd>{v}</dd></div>)}
            </dl>
            {sel.quality?.issues?.length > 0 && <Notice tone="warn" title="Quality issues"><ul className="list-disc pl-4">{sel.quality.issues.map((i: string) => <li key={i}>{i}</li>)}</ul></Notice>}
            <p className="muted text-xs">Annotating creates a label; a different reviewer must approve it before the recording counts as training data.</p>
          </div>
        )}
      </Dialog>
    </div>
  );
}

function Versions() {
  const { user } = useAuth();
  const versions = useQuery<any[]>('/dataset/versions');
  const [v, setV] = useState({ version: '0.1.0', description: '' });
  const [report, setReport] = useState<any>(null);
  const create = useMutation(() => api('/dataset/versions', { body: v }), { invalidates: ['/dataset/versions'], onSuccess: () => toast('Dataset version frozen') });
  const validate = useMutation(() => api('/dataset/validate', { method: 'POST' }), { onSuccess: setReport });
  const exportM = async (id: number, name: string) => {
    const m = await api(`/dataset/versions/${id}/manifest`);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(m, null, 2)], { type: 'application/json' }));
    a.download = `isl-nova-manifest-${name}.json`;
    a.click();
  };
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card title="Validation" subtitle="Integrity, checksums, duplicates, revoked consent, signer independence, imbalance"
        action={<Button icon="check" loading={validate.pending} onClick={() => validate.mutate(undefined)}>Run checks</Button>}>
        {!report ? <p className="muted text-sm">Run the checks to see a report.</p> : (
          <div className="space-y-3 text-sm">
            <p className="flex items-center gap-2"><StatusBadge status={report.ok ? 'succeeded' : 'failed'} />{report.recordings_checked} recordings checked · {fmt.date(report.checked_at)}</p>
            {!report.issues.length ? <p className="text-emerald-200">No issues found.</p> : <ul className="space-y-1.5">{report.issues.map((i: any, k: number) => <li key={k} className="flex gap-2"><Badge tone={i.level === 'error' ? 'bad' : 'warn'}>{i.check}</Badge><span className="text-ink-300">{i.message}</span></li>)}</ul>}
          </div>
        )}
      </Card>
      <Card title="Freeze a dataset version" subtitle="Approved recordings with landmarks and model-training consent, split by signer">
        {can(user, 'dataset:version') ? (
          <div className="space-y-3">
            <ErrorNote error={create.error} />
            <div className="grid gap-3 md:grid-cols-[8rem_1fr]">
              <Field label="Version">{(id) => <Input id={id} value={v.version} onChange={(e) => setV({ ...v, version: e.target.value })} />}</Field>
              <Field label="Description">{(id) => <Input id={id} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />}</Field>
            </div>
            <Button variant="primary" icon="layers" loading={create.pending} onClick={() => create.mutate(undefined)}>Freeze version</Button>
          </div>
        ) : <p className="muted text-sm">Requires the data curator role.</p>}
        <div className="mt-5">
          {!versions.data?.length ? <p className="muted text-sm">No versions yet.</p> : (
            <Table head={['Version', 'Recordings', 'Classes', 'Signers', 'Splits', '']}>
              {versions.data.map((x) => (
                <tr key={x.id}>
                  <td className="px-3 py-2 font-mono">{x.version}</td>
                  <td className="px-3 py-2">{x.summary.recordings}</td>
                  <td className="px-3 py-2">{x.summary.classes}</td>
                  <td className="px-3 py-2">{x.summary.signers}</td>
                  <td className="px-3 py-2 text-xs">{Object.entries(x.summary.splits).map(([k, n]) => `${k} ${n}`).join(' · ')}{x.summary.leakage?.has_leakage && <Badge tone="bad">leakage</Badge>}</td>
                  <td className="px-3 py-2 text-right"><Button size="sm" icon="download" onClick={() => exportM(x.id, x.version)}>Manifest</Button></td>
                </tr>
              ))}
            </Table>
          )}
        </div>
      </Card>
    </div>
  );
}

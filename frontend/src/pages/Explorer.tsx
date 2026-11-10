import { useEffect, useState } from 'react';
import { Icon } from '../components/icons';
import { TranslationsPanel } from '../components/TranslationsPanel';
import { Badge, Button, Card, Dialog, Empty, ErrorNote, Field, Input, Loading, Notice, PageHeader, Select, StatusBadge, Textarea, fmt } from '../components/ui';
import { api, qs } from '../lib/api';
import { invalidate, useMutation, useQuery } from '../lib/query';
import { Link, navigate, useLocation } from '../lib/router';
import { speak } from '../lib/speech';
import { auth, can, toast, useAuth, usePrefs } from '../lib/store';
import type { Category, SignDetail, SignSummary } from '../lib/types';

const LANG_LABEL: Record<string, string> = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' };

function useDebounced<T>(v: T, ms = 250) {
  const [d, setD] = useState(v);
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t); }, [v, ms]);
  return d;
}

export function ExplorerPage() {
  const { user } = useAuth();
  const { search } = useLocation();
  const [q, setQ] = useState(search.get('q') ?? '');
  const [category, setCategory] = useState(search.get('category') ?? '');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const dq = useDebounced(q);
  useEffect(() => setPage(1), [dq, category, status]);
  const cats = useQuery<Category[]>('/signs/categories');
  const key = `/signs${qs({ q: dq, category, status, page, size: 24 })}`;
  const { data, error, loading, refetch } = useQuery<{ items: SignSummary[]; total: number }>(key);
  const pages = data ? Math.max(1, Math.ceil(data.total / 24)) : 1;

  return (
    <div>
      <PageHeader kicker="NOVA Sign Explorer" title="Sign Explorer"
        actions={<>
          {can(user, 'signs:review') && <Button icon="download" onClick={async () => {
            const r = await fetch('/api/v1/signs/review-sheet.csv', { headers: { Authorization: `Bearer ${auth.get().token}` } });
            if (!r.ok) { toast('Could not export the review sheet', 'error'); return; }
            const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'isl-nova-review-sheet.csv'; a.click();
          }}>Review sheet (CSV)</Button>}
          {can(user, 'signs:write') && <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>New sign</Button>}
        </>}>
        Search the 200-slot ISL NOVA vocabulary in English, Hindi or Kannada. Status badges show how far each entry is through qualified review.
      </PageHeader>
      <div className="mb-5"><TranslationsPanel /></div>
      <div className="mb-5 grid gap-3 md:grid-cols-[1fr_auto_auto]">
        <label className="relative">
          <span className="sr-only">Search signs</span>
          <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by meaning, gloss or ID…" className="pl-9" autoFocus />
        </label>
        <Select aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {cats.data?.map((c) => <option key={c.category} value={c.category}>{c.label} ({c.slots})</option>)}
        </Select>
        <Select aria-label="Verification status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {['proposed', 'reference_found', 'review_pending', 'verified', 'rejected'].map((s) => <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>)}
        </Select>
      </div>
      <ErrorNote error={error} retry={refetch} />
      {loading && !data && <Loading rows={6} />}
      {data && (
        <>
          <p className="muted mb-3 text-sm" aria-live="polite">{data.total} sign{data.total === 1 ? '' : 's'}</p>
          {data.items.length === 0 ? (
            <Card><Empty icon="search" title="No signs match">Try a different word, or clear the filters.</Empty></Card>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {data.items.map((s) => (
                <li key={s.sign_id}>
                  <Link to={`/signs/${s.sign_id}`} className="card group flex h-full flex-col gap-3 p-4 transition-colors hover:border-nova-500/50 hover:bg-ink-800">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-mono text-[11px] text-ink-500">{s.sign_id}</p>
                        <p className="mt-0.5 font-display text-lg font-semibold text-fg">{s.canonical_sign_name}</p>
                      </div>
                      {s.bookmarked && <Icon name="bookmark" className="text-nova-300" label="Bookmarked" />}
                    </div>
                    <p className="text-xs text-ink-400">{s.category_label}</p>
                    <div className="mt-auto flex flex-wrap gap-1.5">
                      <StatusBadge status={s.verification_status} />
                      {['hi', 'kn'].map((l) => s.translations[l]?.status === 'verified' && <Badge key={l} tone="ok">{LANG_LABEL[l]}</Badge>)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {pages > 1 && (
            <nav className="mt-6 flex items-center justify-center gap-2" aria-label="Pagination">
              <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-sm text-ink-400">Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </nav>
          )}
        </>
      )}
      <SignForm open={creating} onClose={() => setCreating(false)} categories={cats.data ?? []} />
    </div>
  );
}

type FormState = Partial<SignDetail> & { english_meaning?: string };

function SignForm({ open, onClose, sign, categories }: { open: boolean; onClose: () => void; sign?: SignDetail; categories: Category[] }) {
  const empty: FormState = { sign_id: '', canonical_sign_name: '', category: categories[0]?.category ?? '', english_meaning: '' };
  const [f, setF] = useState<FormState>(sign ?? empty);
  useEffect(() => { if (open) setF(sign ?? empty); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const m = useMutation(async (body: FormState) => {
    const clean = Object.fromEntries(Object.entries(body).filter(([, v]) => v !== '' && v !== null && v !== undefined));
    if (sign) {
      const keys = ['canonical_sign_name', 'category', 'linguistic_description', 'dominant_hand', 'hands_required', 'movement_type', 'body_movement', 'non_manual_cue', 'regional_variation', 'annotation_notes'];
      return api(`/signs/${sign.sign_id}`, { method: 'PATCH', body: Object.fromEntries(keys.filter((k) => k in clean).map((k) => [k, clean[k]])) });
    }
    return api('/signs', { body: clean });
  }, {
    invalidates: ['/signs', '/dashboard', '/dataset'],
    onSuccess: (r: SignDetail) => { toast(sign ? 'Sign updated' : `Created ${r.sign_id}`); onClose(); if (!sign) navigate(`/signs/${r.sign_id}`); },
  });
  const set = (k: keyof FormState) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open={open} onClose={onClose} title={sign ? `Edit ${sign.sign_id}` : 'New vocabulary entry'} wide
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={m.pending} onClick={() => m.mutate(f)}>{sign ? 'Save changes' : 'Create sign'}</Button></>}>
      <div className="space-y-4">
        <ErrorNote error={m.error} />
        {!sign && <Notice title="Sign IDs are permanent">New entries start as <b>proposed</b> and must be reviewed. IDs are never reused, even if retired.</Notice>}
        <div className="grid gap-4 md:grid-cols-2">
          {!sign && <Field label="Sign ID" hint="Format ISL201, ISL202…">{(id) => <Input id={id} value={f.sign_id ?? ''} onChange={set('sign_id')} placeholder="ISL201" />}</Field>}
          <Field label="Canonical name">{(id) => <Input id={id} value={f.canonical_sign_name ?? ''} onChange={set('canonical_sign_name')} />}</Field>
          <Field label="Category">{(id) => <Select id={id} value={f.category ?? ''} onChange={set('category')}>{categories.map((c) => <option key={c.category} value={c.category}>{c.label}</option>)}</Select>}</Field>
          {!sign && <Field label="English meaning (draft)">{(id) => <Input id={id} value={f.english_meaning ?? ''} onChange={set('english_meaning')} />}</Field>}
          <Field label="Hands required">{(id) => <Select id={id} value={f.hands_required ?? ''} onChange={set('hands_required')}><option value="">Unknown</option><option value="one">One hand</option><option value="two">Two hands</option></Select>}</Field>
          <Field label="Movement">{(id) => <Select id={id} value={f.movement_type ?? ''} onChange={set('movement_type')}><option value="">Unknown</option><option value="static">Static</option><option value="dynamic">Dynamic</option></Select>}</Field>
          <Field label="Dominant hand">{(id) => <Select id={id} value={f.dominant_hand ?? ''} onChange={set('dominant_hand')}><option value="">Unknown</option><option value="right">Right</option><option value="left">Left</option><option value="either">Either</option></Select>}</Field>
        </div>
        <Field label="Linguistic description" hint="Handshape, location, movement, orientation. Leave blank if unknown, never guess.">{(id) => <Textarea id={id} value={f.linguistic_description ?? ''} onChange={set('linguistic_description')} />}</Field>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Non-manual cue">{(id) => <Textarea id={id} rows={2} value={f.non_manual_cue ?? ''} onChange={set('non_manual_cue')} />}</Field>
          <Field label="Regional variation">{(id) => <Textarea id={id} rows={2} value={f.regional_variation ?? ''} onChange={set('regional_variation')} />}</Field>
        </div>
        <Field label="Annotation notes">{(id) => <Textarea id={id} rows={2} value={f.annotation_notes ?? ''} onChange={set('annotation_notes')} />}</Field>
      </div>
    </Dialog>
  );
}

const NEXT: Record<string, string[]> = {
  proposed: ['reference_found', 'review_pending', 'rejected'], reference_found: ['review_pending', 'rejected'],
  review_pending: ['verified', 'rejected', 'reference_found'], verified: ['review_pending'], rejected: ['review_pending'],
};

export function SignDetailPage({ id }: { id: string }) {
  const { user } = useAuth();
  const prefs = usePrefs();
  const key = `/signs/${id}`;
  const { data: s, error, loading, refetch } = useQuery<SignDetail>(key);
  const cats = useQuery<Category[]>('/signs/categories');
  const [editing, setEditing] = useState(false);
  const [review, setReview] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [tr, setTr] = useState<{ lang: string; text: string; status: string } | null>(null);
  const [report, setReport] = useState(false);
  const [reportText, setReportText] = useState('');

  const inv = [key, '/signs', '/dashboard', '/dataset', '/learning'];
  const [check, setCheck] = useState({ reference_reviewed: false, form_matches_reference: false, meaning_confirmed: false });
  const reviewM = useMutation((b: { to_status: string; note: string }) => api(`${key}/review`, { body: b.to_status === 'verified' ? { ...b, checklist: check } : b }), { invalidates: inv, onSuccess: () => { toast('Status updated'); setReview(null); setNote(''); setCheck({ reference_reviewed: false, form_matches_reference: false, meaning_confirmed: false }); } });
  const trM = useMutation((b: { lang: string; text: string; status: string }) => api(`${key}/translations/${b.lang}`, { method: 'PUT', body: { text: b.text, status: b.status } }), { invalidates: inv, onSuccess: () => { toast('Translation saved'); setTr(null); } });
  const bmM = useMutation((on: boolean) => api(`/bookmarks/${id}`, { method: on ? 'PUT' : 'DELETE' }), { invalidates: [key, '/bookmarks', '/signs'] });
  const retireM = useMutation((retire: boolean) => api(retire ? key : `${key}/restore`, { method: retire ? 'DELETE' : 'POST' }), { invalidates: inv, onSuccess: (r: { retired: boolean }) => toast(r.retired ? 'Sign retired' : 'Sign restored') });
  const fbM = useMutation((message: string) => api('/feedback', { body: { kind: 'correction', sign_id: id, message } }), { onSuccess: () => { toast('Thanks, your correction was sent to reviewers'); setReport(false); setReportText(''); } });

  if (loading && !s) return <Loading rows={6} />;
  if (error) return <ErrorNote error={error} retry={refetch} />;
  if (!s) return null;
  const canWrite = can(user, 'signs:write');

  return (
    <div className="space-y-5">
      <Link to="/signs" className="inline-flex items-center gap-1 text-sm text-ink-400 hover:text-fg"><Icon name="chevron" size={14} className="rotate-180" />All signs</Link>
      <PageHeader kicker={`${s.sign_id} · ${s.category_label}`} title={s.canonical_sign_name}
        actions={<>
          {user && <Button icon="bookmark" variant={s.bookmarked ? 'primary' : 'secondary'} onClick={() => bmM.mutate(!s.bookmarked)} aria-pressed={s.bookmarked}>{s.bookmarked ? 'Bookmarked' : 'Bookmark'}</Button>}
          <Button icon="flag" variant="ghost" onClick={() => setReport(true)}>Report a correction</Button>
          {canWrite && <Button icon="edit" onClick={() => setEditing(true)}>Edit sign</Button>}
          {canWrite && <Button variant="ghost" icon={s.retired ? 'undo' : 'trash'} onClick={() => retireM.mutate(!s.retired)} loading={retireM.pending}>{s.retired ? 'Restore' : 'Retire'}</Button>}
        </>}>
        <span className="flex flex-wrap items-center gap-2"><StatusBadge status={s.verification_status} /><StatusBadge status={s.data_readiness} />{s.retired && <Badge tone="bad">Retired</Badge>}</span>
      </PageHeader>
      <ErrorNote error={retireM.error} />
      {s.verification_status !== 'verified' && (
        <Notice tone="warn" title="Not yet verified by a qualified ISL reviewer">
          The English gloss comes from the source dataset folder name. The ISL form, regional variants and non-manual features have not been confirmed.
        </Notice>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Meanings" subtitle="Only reviewer-verified translations are used in quizzes and quick phrases">
          <ul className="divide-y divide-ink-700">
            {(['en', 'hi', 'kn'] as const).map((l) => {
              const t = s.translations[l];
              return (
                <li key={l} className="flex flex-wrap items-center gap-3 py-3">
                  <span className="w-20 text-sm text-ink-400">{LANG_LABEL[l]}</span>
                  <span className={`flex-1 text-lg ${t?.text ? 'text-fg' : 'text-ink-500 italic'}`}>{t?.text || 'Pending review'}</span>
                  <StatusBadge status={t?.status ?? 'pending'} />
                  {t?.text && <Button size="sm" variant="ghost" icon="speaker" aria-label={`Speak ${LANG_LABEL[l]} meaning`} onClick={() => { const r = speak(t.text, l, prefs.speechRate); if (r.reason) toast(r.reason, 'info'); }} />}
                  {can(user, 'translations:write') && <Button size="sm" icon="edit" aria-label={`Edit ${LANG_LABEL[l]} meaning`} onClick={() => setTr({ lang: l, text: t?.text ?? '', status: t?.status === 'verified' ? 'verified' : 'draft' })}>Edit</Button>}
                </li>
              );
            })}
          </ul>
        </Card>

        <Card title="Review workflow">
          <ol className="relative space-y-3 border-l border-ink-700 pl-4 text-sm">
            {s.verification_events.length === 0 && <li className="muted">No events yet.</li>}
            {s.verification_events.map((e, i) => (
              <li key={i}>
                <span className="absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-ink-850 bg-nova-400" />
                <StatusBadge status={e.to_status} /> <span className="muted text-xs">{fmt.date(e.created_at)}{e.actor ? ` · ${e.actor}` : ''}</span>
                <p className="mt-1 text-ink-300">{e.note}</p>
              </li>
            ))}
          </ol>
          {can(user, 'signs:review') && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-ink-700 pt-4">
              {NEXT[s.verification_status]?.map((t) => (
                <Button key={t} size="sm" variant={t === 'verified' ? 'primary' : t === 'rejected' ? 'danger' : 'secondary'} onClick={() => setReview(t)}
                  disabled={t === 'verified' && !user?.roles.includes('linguist')} title={t === 'verified' && !user?.roles.includes('linguist') ? 'Requires the linguist role' : undefined}>
                  → {t.replaceAll('_', ' ')}
                </Button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Linguistic description">
          <dl className="space-y-3 text-sm">
            {([['Description', s.linguistic_description], ['Hands', s.hands_required], ['Movement', s.movement_type], ['Dominant hand', s.dominant_hand], ['Body movement', s.body_movement], ['Non-manual cue', s.non_manual_cue], ['Regional variation', s.regional_variation], ['Notes', s.annotation_notes]] as const).map(([k, v]) => (
              <div key={k}><dt className="label">{k}</dt><dd className={v ? 'mt-0.5 text-ink-100' : 'mt-0.5 italic text-ink-500'}>{v || 'Not yet documented'}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title="Reference sources" subtitle="Licence and training permission per source">
          <ul className="space-y-3 text-sm">
            {s.references.map((r) => (
              <li key={r.id} className="rounded-lg border border-ink-700 p-3">
                <p className="font-medium text-fg">{r.source_name} <Badge tone="signal">{r.license}</Badge></p>
                {r.notes && <p className="muted mt-1 text-xs">{r.notes}</p>}
                {r.training_permitted && <p className="mt-1 text-xs text-ink-300">Training: {r.training_permitted}</p>}
                {r.source_url && <a href={r.source_url} target="_blank" rel="noreferrer noopener" className="mt-1 inline-block text-xs text-nova-300 hover:underline">{r.doi ? `doi:${r.doi}` : r.source_url}</a>}
              </li>
            ))}
          </ul>
          <p className="muted mt-3 text-xs">Reference videos are not mirrored here. Open the source to view them under its licence.</p>
        </Card>
        <Card title="Data">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-ink-400">External videos (train/val/test)</dt><dd>{s.external_train_videos}/{s.external_val_videos}/{s.external_test_videos}</dd></div>
            {Object.entries(s.recordings).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-ink-400">Local · {k.replaceAll('_', ' ')}</dt><dd>{v}</dd></div>)}
          </dl>
          {!Object.keys(s.recordings).length && <p className="muted mt-2 text-xs">No local recordings yet.</p>}
          <p className="label mb-2 mt-5">Related signs</p>
          <div className="flex flex-wrap gap-1.5">{s.related.map((r) => <Link key={r.sign_id} to={`/signs/${r.sign_id}`} className="rounded-full border border-ink-600 px-2.5 py-1 text-xs text-ink-200 hover:border-nova-400 hover:text-fg">{r.canonical_sign_name}</Link>)}</div>
        </Card>
      </div>

      <SignForm open={editing} onClose={() => setEditing(false)} sign={s} categories={cats.data ?? []} />
      <Dialog open={!!review} onClose={() => setReview(null)} title={`Move to "${review?.replaceAll('_', ' ')}"`}
        footer={<><Button variant="ghost" onClick={() => setReview(null)}>Cancel</Button><Button variant="primary" loading={reviewM.pending} disabled={note.trim().length < 3 || (review === 'verified' && !(check.reference_reviewed && check.form_matches_reference && check.meaning_confirmed))} onClick={() => reviewM.mutate({ to_status: review!, note })}>Confirm</Button></>}>
        <div className="space-y-4">
          <ErrorNote error={reviewM.error} />
          {review === 'verified' && (() => {
            const missing = (['linguistic_description', 'hands_required', 'movement_type'] as const).filter((f) => !s[f]);
            return (
              <>
                {missing.length > 0 && <Notice tone="warn" title="Document the sign first">Missing: {missing.map((m) => m.replaceAll('_', ' ')).join(', ')}. Use <b>Edit sign</b> to add them.</Notice>}
                <fieldset className="space-y-2 rounded-xl border border-ink-700 p-3 text-sm">
                  <legend className="label px-1">Verification checklist (all required)</legend>
                  {([['reference_reviewed', 'I watched the licensed reference recording(s) for this sign'], ['form_matches_reference', 'Handshape, location, movement and orientation match the reference'], ['meaning_confirmed', 'The English meaning is an accurate gloss for this ISL sign']] as const).map(([k, label]) => (
                    <label key={k} className="flex items-start gap-2"><input type="checkbox" className="mt-1 accent-nova-500" checked={check[k]} onChange={(e) => setCheck({ ...check, [k]: e.target.checked })} />{label}</label>
                  ))}
                </fieldset>
              </>
            );
          })()}
          <Field label="Review note" hint="Required. Recorded permanently in the verification log.">{(fid) => <Textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        </div>
      </Dialog>
      <Dialog open={!!tr} onClose={() => setTr(null)} title={`${tr ? LANG_LABEL[tr.lang] : ''} meaning`}
        footer={<><Button variant="ghost" onClick={() => setTr(null)}>Cancel</Button><Button variant="primary" loading={trM.pending} onClick={() => tr && trM.mutate(tr)}>Save</Button></>}>
        {tr && (
          <div className="space-y-4">
            <ErrorNote error={trM.error} />
            <Field label="Meaning">{(fid) => <Input id={fid} value={tr.text} onChange={(e) => setTr({ ...tr, text: e.target.value })} lang={tr.lang} />}</Field>
            <Field label="Status" hint="Only users with the linguist role can mark a meaning verified.">{(fid) => <Select id={fid} value={tr.status} onChange={(e) => setTr({ ...tr, status: e.target.value })}><option value="draft">Draft</option><option value="verified">Verified</option><option value="rejected">Rejected</option></Select>}</Field>
          </div>
        )}
      </Dialog>
      <Dialog open={report} onClose={() => setReport(false)} title="Report a correction"
        footer={<><Button variant="ghost" onClick={() => setReport(false)}>Cancel</Button><Button variant="primary" loading={fbM.pending} disabled={reportText.trim().length < 3} onClick={() => fbM.mutate(reportText)}>Send</Button></>}>
        <ErrorNote error={fbM.error} />
        <Field label="What should change?" hint="Reviewers see this in the feedback inbox.">{(fid) => <Textarea id={fid} rows={4} value={reportText} onChange={(e) => setReportText(e.target.value)} />}</Field>
      </Dialog>
    </div>
  );
}

export function useBookmarks() {
  const { user } = useAuth();
  return useQuery<{ sign_id: string; canonical_sign_name: string }[]>(user ? '/bookmarks' : null);
}

export const _invalidateSigns = () => invalidate('/signs');

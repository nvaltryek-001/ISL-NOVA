import { useEffect, useState } from 'react';
import { Icon } from '../components/icons';
import { Badge, Button, Card, Empty, Field, Input, Notice, PageHeader, Select, Textarea } from '../components/ui';
import { api, qs } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { speak, speechSupported } from '../lib/speech';
import { toast, useAuth, usePrefs } from '../lib/store';
import type { SignSummary } from '../lib/types';

type Phrase = { id: number; text: string; sign_ids: string[]; language: string; is_quick: boolean; user_id: number | null };
const LANGS = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' } as const;
type Lang = keyof typeof LANGS;

export function CommunicatePage() {
  const { user } = useAuth();
  const prefs = usePrefs();
  const [lang, setLang] = useState<Lang>(prefs.language);
  const [q, setQ] = useState('');
  const [seq, setSeq] = useState<SignSummary[]>([]);
  const [text, setText] = useState('');
  const [edited, setEdited] = useState(false);
  const results = useQuery<{ items: SignSummary[] }>(q.trim().length > 0 ? `/signs${qs({ q, size: 8 })}` : null);
  const phrases = useQuery<Phrase[]>('/phrases');
  const save = useMutation((b: { sign_ids: string[]; text: string; language: string }) => api('/phrases', { body: b }), { invalidates: ['/phrases'], onSuccess: () => toast('Phrase saved') });
  const del = useMutation((id: number) => api(`/phrases/${id}`, { method: 'DELETE' }), { invalidates: ['/phrases'] });

  const meaningOf = (s: SignSummary) => {
    const t = s.translations[lang];
    if (t?.text) return { text: t.text, verified: t.status === 'verified' };
    return { text: s.translations.en?.text || s.canonical_sign_name, verified: false };
  };
  useEffect(() => { if (!edited) setText(seq.map((s) => meaningOf(s).text).join(' ')); }, [seq, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const unverified = seq.filter((s) => !meaningOf(s).verified).length;

  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Communication Workspace" title="Communication">
        Compose a message from isolated sign meanings, edit it into natural language, then speak, copy or share it.
      </PageHeader>
      <Notice title="This is a word-by-word composer, not an ISL translator">
        ISL has its own grammar. Joining isolated sign meanings does not produce a grammatical translation; edit the text before relying on it.
        Continuous sign recognition and grammar-aware translation are open research problems not provided here.
      </Notice>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card title="1 · Pick signs">
          <label className="relative block">
            <span className="sr-only">Search signs</span>
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <Input className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a meaning, e.g. hello, school, mother…" />
          </label>
          <ul className="mt-3 space-y-1" aria-label="Search results">
            {results.data?.items.map((s) => (
              <li key={s.sign_id}>
                <button className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-ink-700" onClick={() => { setSeq([...seq, s]); setEdited(false); }}>
                  <span>{s.canonical_sign_name} <span className="ml-1 font-mono text-xs text-ink-500">{s.sign_id}</span></span>
                  <Icon name="plus" className="text-nova-300" />
                </button>
              </li>
            ))}
            {q && results.data?.items.length === 0 && <li className="muted px-3 py-2 text-sm">No matching sign.</li>}
          </ul>
        </Card>
        <Card title="2 · Compose & speak" action={
          <Select aria-label="Output language" value={lang} onChange={(e) => { setLang(e.target.value as Lang); setEdited(false); }} className="h-9 w-auto py-0">
            {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>}>
          <div className="flex min-h-12 flex-wrap gap-2 rounded-xl border border-ink-700 bg-ink-900 p-2" aria-label="Sign sequence">
            {seq.length === 0 && <span className="muted px-2 py-1 text-sm">Signs you pick appear here, in order.</span>}
            {seq.map((s, i) => {
              const m = meaningOf(s);
              return (
                <span key={i} className="inline-flex items-center gap-1.5 rounded-lg bg-ink-800 py-1 pl-2.5 pr-1 text-sm ring-1 ring-ink-600">
                  {m.text}{!m.verified && <span className="size-1.5 rounded-full bg-amber-400" title="Meaning not verified" />}
                  <button className="rounded p-0.5 text-ink-400 hover:bg-ink-700 hover:text-white" onClick={() => { setSeq(seq.filter((_, j) => j !== i)); setEdited(false); }} aria-label={`Remove ${m.text}`}><Icon name="close" size={14} /></button>
                </span>
              );
            })}
          </div>
          {unverified > 0 && <p className="mt-2 text-xs text-amber-200">{unverified} meaning{unverified > 1 ? 's are' : ' is'} unverified or missing in {LANGS[lang]}; English source glosses are shown instead.</p>}
          <div className="mt-4">
            <Field label="Message (editable)">{(id) => <Textarea id={id} rows={4} lang={lang} value={text} onChange={(e) => { setText(e.target.value); setEdited(true); }} className="text-lg" />}</Field>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" icon="speaker" disabled={!text.trim() || !speechSupported()} onClick={() => { const r = speak(text, lang, prefs.speechRate); if (r.reason) toast(r.reason, 'info'); }}>Speak</Button>
            <Button icon="copy" disabled={!text.trim()} onClick={() => { navigator.clipboard?.writeText(text); toast('Copied to clipboard'); }}>Copy</Button>
            {'share' in navigator && <Button icon="upload" disabled={!text.trim()} onClick={() => navigator.share({ text }).catch(() => {})}>Share</Button>}
            <Button icon="bookmark" disabled={!user || !seq.length || !text.trim()} title={!user ? 'Sign in to save phrases' : undefined} loading={save.pending}
              onClick={() => save.mutate({ sign_ids: seq.map((s) => s.sign_id), text, language: lang })}>Save phrase</Button>
            <Button variant="ghost" icon="trash" disabled={!seq.length && !text} onClick={() => { setSeq([]); setText(''); setEdited(false); }}>Clear</Button>
          </div>
          {!speechSupported() && <p className="muted mt-2 text-xs">Speech synthesis is not available in this browser.</p>}
        </Card>
      </div>
      <Card title="Saved & quick phrases" subtitle="Quick phrases are curated by reviewers from verified signs and appear in kiosk mode">
        {!phrases.data?.length ? <Empty icon="chat" title="No phrases yet">{user ? 'Compose a message and save it.' : 'Sign in to save your own phrases.'}</Empty> : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {phrases.data.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-2 rounded-xl border border-ink-700 p-3">
                <div>
                  <p className="text-white" lang={p.language}>{p.text}</p>
                  <p className="mt-1 flex gap-1.5 text-xs text-ink-500">{p.is_quick && <Badge tone="ok">Quick phrase</Badge>}<span>{LANGS[p.language as Lang]} · {p.sign_ids.length} signs</span></p>
                </div>
                <div className="flex shrink-0">
                  <Button size="sm" variant="ghost" icon="speaker" aria-label="Speak phrase" onClick={() => speak(p.text, p.language, prefs.speechRate)} />
                  {user && p.user_id === user.id && <Button size="sm" variant="ghost" icon="trash" aria-label="Delete phrase" onClick={() => del.mutate(p.id)} />}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

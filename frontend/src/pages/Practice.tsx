// Practice Coach: copy a reference sign, capture an attempt and get per-part feedback.
import { useCallback, useEffect, useRef, useState } from 'react';
import { CameraStage } from '../components/CameraStage';
import { SignAnimation } from '../components/SignAnimation';
import { Badge, Button, Card, Empty, Input, Meter, Notice, PageHeader, StatusBadge } from '../components/ui';
import { useT } from '../i18n';
import { api } from '../lib/api';
import type { Frame } from '../lib/features';
import { useQuery } from '../lib/query';
import { useLocation } from '../lib/router';
import { useAuth, usePrefs } from '../lib/store';

type SignHit = { sign_id: string; canonical_sign_name: string; translations: Record<string, { text: string; status: string }> };
type Part = { part: string; label: string; ratio: number; status: 'good' | 'check' | 'different' };
type Score = { state: string; score: number | null; parts: Part[]; tips: string[]; reasons?: string[]; note?: string;
  model?: { state: string; matches_target: boolean; top: { sign_id: string; label: string; probability: number }[] } };

const CAPTURE_MS = 2500;

export function PracticePage() {
  const t = useT();
  const { language } = usePrefs();
  const status = useQuery<{ available: boolean; classes: number }>('/practice/status');
  const [q, setQ] = useState('');
  const [sign, setSign] = useState<SignHit | null>(null);
  const preset = useLocation().search.get('sign');  // e.g. from the review queue or a teacher's hard-sign list
  useEffect(() => {
    if (!preset) return;
    api<SignHit>(`/signs/${encodeURIComponent(preset)}`).then(setSign).catch(() => undefined);
  }, [preset]);
  const hits = useQuery<{ items: SignHit[] }>(`/signs?size=8&q=${encodeURIComponent(q)}`);
  const capture = useRef<{ f: Frame; a: number }[] | null>(null);
  const [phase, setPhase] = useState<'idle' | 'countdown' | 'capturing' | 'scoring'>('idle');
  const [count, setCount] = useState(0);
  const [result, setResult] = useState<Score | null>(null);
  const signedIn = !!useAuth().user;
  const [ready, setReady] = useState(false);

  const onFrame = useCallback((f: Frame, a: number) => { capture.current?.push({ f, a }); }, []);
  const onState = useCallback((s: string, ex: string) => setReady(s === 'live' && ex === 'ready'), []);

  const attempt = () => {
    if (!sign) return;
    setResult(null);
    let n = 3;
    setPhase('countdown'); setCount(n);
    const iv = setInterval(() => {
      n -= 1;
      if (n > 0) { setCount(n); return; }
      clearInterval(iv);
      capture.current = [];
      setPhase('capturing');
      setTimeout(async () => {
        const frames = capture.current ?? [];
        capture.current = null;
        setPhase('scoring');
        try {
          const r = await api<Score>('/practice/score', { body: { sign_id: sign.sign_id, frames: frames.map((x) => x.f), aspect: frames.at(-1)?.a ?? 4 / 3 } });
          setResult(r);
          // signed-in learners: count the attempt toward progress, streaks and badges
          if (signedIn && typeof r.score === 'number') {
            api('/learning/attempts', { body: { sign_id: sign.sign_id, mode: 'coach', correct: r.score >= 70 } }).catch(() => undefined);
          }
        } catch (e) {
          setResult({ state: 'error', score: null, parts: [], tips: [(e as Error).message] });
        } finally { setPhase('idle'); }
      }, CAPTURE_MS);
    }, 1000);
  };

  const meaning = sign?.translations?.[language]?.text || sign?.canonical_sign_name;
  return (
    <div>
      <PageHeader title="Practice Coach">
        {t('Watch the reference, then sign it yourself. The coach compares your hand shape, position and movement with INCLUDE reference recordings and tells you what to adjust.')}
      </PageHeader>
      {status.data && !status.data.available && <div className="mb-5"><Notice tone="warn" title="Reference data not installed">{t('Run scripts/fetch_references.py (the setup scripts do this) to enable the Practice Coach.')}</Notice></div>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-5">
          <Card title="1 · Choose a sign">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('Search by meaning, gloss or ID…')} aria-label={t('Search signs')} />
            <div className="mt-3 flex flex-wrap gap-2">
              {hits.data?.items.map((s) => (
                <button key={s.sign_id} onClick={() => { setSign(s); setResult(null); }}
                  className={`rounded-xl border px-3 py-2 text-left text-sm ${sign?.sign_id === s.sign_id ? 'border-nova-400 bg-nova-500/10 text-fg' : 'border-ink-700 text-ink-200 hover:bg-ink-800'}`}>
                  <span className="block font-medium">{s.translations?.[language]?.text || s.canonical_sign_name}</span>
                  <span className="text-xs text-ink-400">{s.sign_id} · {s.canonical_sign_name}</span>
                </button>
              ))}
            </div>
          </Card>
          <Card title="2 · Watch the reference" subtitle={sign ? `${sign.sign_id} · ${meaning}` : undefined}>
            {sign ? <SignAnimation signId={sign.sign_id} size="lg" /> : <Empty icon="hand" title="Choose a sign to see its reference" />}
          </Card>
        </div>
        <div className="space-y-5">
          <Card title="3 · Your turn" action={phase === 'countdown' ? <Badge tone="warn">{count}</Badge> : phase === 'capturing' ? <Badge tone="bad">{t('Recording')}…</Badge> : phase === 'scoring' ? <Badge tone="nova">{t('Scoring')}…</Badge> : null}>
            <CameraStage onFrame={onFrame} onState={onState} large />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button variant="primary" size="lg" icon="record" disabled={!sign || !ready || phase !== 'idle'} onClick={attempt}>Try it (3-2-1)</Button>
              <span className="muted text-sm">{!sign ? t('Choose a sign first.') : !ready ? t('Start the camera first.') : t('Sign once during the 2.5 s window.')}</span>
            </div>
          </Card>
          {result && <ResultCard r={result} />}
        </div>
      </div>
    </div>
  );
}

function ResultCard({ r }: { r: Score }) {
  const t = useT();
  if (r.state !== 'scored') {
    return <Card title="Result"><Notice tone="warn" title={r.state === 'insufficient_input' ? 'Not enough usable input' : 'Could not score'}>{r.tips.concat(r.reasons ?? []).join(' ')}</Notice></Card>;
  }
  const s = r.score ?? 0;
  const tone = s >= 70 ? 'ok' : s >= 40 ? 'warn' : 'bad';
  return (
    <Card title="Result" subtitle={r.note}>
      <div className="flex flex-wrap items-center gap-6">
        <div className="text-center">
          <p className={`text-5xl font-semibold ${tone === 'ok' ? 'text-emerald-400' : tone === 'warn' ? 'text-amber-400' : 'text-rose-400'}`}>{Math.round(s)}</p>
          <p className="muted text-xs">{t('similarity / 100')}</p>
        </div>
        {r.model && (
          <div className="text-sm">
            <p className="muted text-xs">{t('The recognition model read your attempt as')}</p>
            <p className="font-medium text-fg">{r.model.top[0]?.label ?? '—'} <StatusBadge status={r.model.state} /></p>
            <p className="text-xs">{r.model.matches_target ? t('This matches the sign you practised.') : t('This differs from the sign you practised.')}</p>
          </div>
        )}
      </div>
      <ul className="mt-4 space-y-2">
        {r.parts.filter((p) => p.part !== 'presence').map((p) => (
          <li key={p.part} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-sm">
            <div>
              <span className="text-ink-100">{t(p.label)}</span>
              <Meter value={Math.max(0, Math.min(100, 100 - (p.ratio - 1) * 60))} max={100} label={t(p.label)} tone={p.status === "good" ? "ok" : "warn"} />
            </div>
            <Badge tone={p.status === 'good' ? 'ok' : p.status === 'check' ? 'warn' : 'bad'}>{t(p.status === 'good' ? 'Good' : p.status === 'check' ? 'Check' : 'Different')}</Badge>
          </li>
        ))}
      </ul>
      <div className="mt-4 rounded-xl border border-ink-700 bg-ink-850 p-3">
        <p className="mb-1 text-sm font-medium text-fg">{t('Tips')}</p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-200">{r.tips.map((x) => <li key={x}>{t(x)}</li>)}</ul>
      </div>
    </Card>
  );
}

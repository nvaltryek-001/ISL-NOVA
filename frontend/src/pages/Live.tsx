import { useCallback, useEffect, useRef, useState } from 'react';
import { ProbBars } from '../components/charts';
import { CameraStage } from '../components/CameraStage';
import { Icon } from '../components/icons';
import { Badge, Button, Card, Dialog, Empty, Field, Input, Notice, PageHeader, Select, StatusBadge, Tabs } from '../components/ui';
import { api, qs } from '../lib/api';
import type { Frame } from '../lib/features';
import { extractFeatures, windowQuality } from '../lib/features';
import { ApiError } from '../lib/api';
import { loadWebModel } from '../lib/webModel';
import { useT } from '../i18n';
import type { CameraState } from '../lib/landmarks';
import { useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { speak } from '../lib/speech';
import { toast, useAuth, usePrefs } from '../lib/store';
import type { ModelInfo, Prediction, SignSummary } from '../lib/types';

const WINDOW_MS = 2000; // continuous mode: classify the last 2 s, independent of camera frame rate
const INTERVAL_MS = 750;
const CAPTURE_OPTIONS = [1.5, 2.5, 3.5];
const LANGS = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' } as const;

type Mode = 'capture' | 'continuous';

export function LivePage() {
  const { user } = useAuth();
  const prefs = usePrefs();
  const t = useT();
  const model = useQuery<ModelInfo>('/model/info');
  const buffer = useRef<{ f: Frame; a: number; t: number }[]>([]);
  const [captureSec, setCaptureSec] = useState(2.5);
  const [useCountdown, setUseCountdown] = useState(true);
  const capture = useRef<{ f: Frame; a: number }[] | null>(null);
  const [mode, setMode] = useState<Mode>('capture');
  const [cam, setCam] = useState<{ s: CameraState; ex: string }>({ s: 'idle', ex: 'loading' });
  const [running, setRunning] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [pred, setPred] = useState<Prediction | null>(null);
  const [smoothed, setSmoothed] = useState<{ sign_id: string; label: string; p: number }[]>([]);
  const ema = useRef<Map<string, { label: string; p: number }>>(new Map());
  const [lang, setLang] = useState<keyof typeof LANGS>(prefs.language);
  const [session, setSession] = useState<(Prediction & { at: string })[]>([]);
  const [correcting, setCorrecting] = useState(false);
  const inflight = useRef(false);
  const [where, setWhere] = useState<'server' | 'device'>('server');

  /** Recognition on this device with the exported model (works offline once loaded). */
  const predictOnDevice = useCallback(async (frames: { f: Frame; a: number }[]): Promise<Prediction> => {
    const m = await loadWebModel();
    const fr = extractFeatures(frames.map((x) => x.f), frames[frames.length - 1].a);
    if (fr.status !== 'ok') return { state: 'insufficient_input', top: [], reasons: fr.reasons, model_id: m.header.model_id };
    const t0 = performance.now();
    const d = m.decide(m.predictProba(fr.features), 5);
    return { state: d.state as Prediction['state'], top: d.top, reasons: [], model_id: m.header.model_id,
      synthetic: m.header.synthetic, latency_ms: Math.round((performance.now() - t0) * 10) / 10 };
  }, []);

  const onFrame = useCallback((f: Frame, a: number, t: number) => {
    buffer.current.push({ f, a, t });
    while (buffer.current.length && t - buffer.current[0].t > 6000) buffer.current.shift();
    capture.current?.push({ f, a });
  }, []);
  const onState = useCallback((s: CameraState, ex: string) => setCam({ s, ex }), []);

  const send = useCallback(async (frames: { f: Frame; a: number }[]) => {
    if (inflight.current) return;
    if (!frames.length) {
      // never fail silently: no landmark frames were processed during the capture window
      setPred({ state: 'insufficient_input', top: [], reasons: ['No camera frames were processed during the capture. Check that the camera preview is moving and hand tracking is active.'] });
      return;
    }
    inflight.current = true;
    try {
      let r: Prediction;
      if (where === 'device') r = await predictOnDevice(frames);
      else {
        try {
          r = await api<Prediction>('/predict/sequence', { body: { frames: frames.map((x) => x.f), aspect: frames[frames.length - 1].a, top_k: 5 } });
        } catch (e) {
          if (!(e instanceof ApiError && e.code === 'offline')) throw e;
          r = await predictOnDevice(frames);  // server unreachable: fall back to the on-device model
          toast(t('Server unreachable: recognised on this device'), 'info');
        }
      }
      setPred(r);
      // exponential smoothing of probabilities across successive windows (display only)
      const m = ema.current;
      for (const v of m.values()) v.p *= 0.5;
      for (const t of r.top) { const cur = m.get(t.sign_id); m.set(t.sign_id, { label: t.label, p: (cur?.p ?? 0) + 0.5 * t.probability }); }
      setSmoothed([...m.entries()].map(([sign_id, v]) => ({ sign_id, ...v })).sort((a, b) => b.p - a.p).slice(0, 5));
      if (mode === 'capture' || r.state === 'recognized') setSession((s) => [{ ...r, at: new Date().toISOString() }, ...s].slice(0, 30));
    } catch (e) {
      toast((e as Error).message, 'error');
    } finally {
      inflight.current = false;
    }
  }, [mode, where, predictOnDevice, t]);

  // continuous mode: classify a sliding window
  useEffect(() => {
    if (!running || mode !== 'continuous') return;
    const t = setInterval(() => {
      const end = performance.now();
      const w = buffer.current.filter((x) => end - x.t <= WINDOW_MS);
      if (w.length < 8) return;
      if (windowQuality(w.map((x) => x.f)).hands < 0.25) { setPred({ state: 'insufficient_input', top: [], reasons: ['Hands not visible in enough frames'] }); return; }
      send(w);
    }, INTERVAL_MS);
    return () => clearInterval(t);
  }, [running, mode, send]);

  const startCapture = () => {
    const record = () => {
      capture.current = [];
      setCountdown(-1); // capturing
      setTimeout(() => {
        const frames = capture.current ?? [];
        capture.current = null;
        setCountdown(-2); // classifying
        send(frames).finally(() => setCountdown(0));
      }, captureSec * 1000);
    };
    if (!useCountdown) { record(); return; }
    let n = 3;
    setCountdown(n);
    const t = setInterval(() => {
      n -= 1;
      if (n > 0) { setCountdown(n); return; }
      clearInterval(t);
      record();
    }, 700);
  };

  const top = pred?.top[0];
  const meaning = top?.meanings?.[lang];
  const unavailable = model.data && !model.data.available;
  const ready = cam.s === 'live' && cam.ex === 'ready';

  const save = async () => {
    if (!pred) return;
    if (!user) { toast('Sign in to save history', 'info'); return; }
    await api('/history', { body: { state: pred.state, model_id: pred.model_id, top: pred.top, chosen_sign: pred.state === 'recognized' && top?.sign_id.startsWith('ISL') ? top.sign_id : null } });
    toast('Saved to your history');
  };

  return (
    <div>
      <PageHeader kicker="NOVA Live Recognition Studio" title="Live Recognition"
        actions={<Tabs value={mode} onChange={(m) => { setMode(m); setRunning(false); }} tabs={[{ id: 'capture', label: 'Capture one sign' }, { id: 'continuous', label: 'Continuous' }]} />}>
        Isolated-sign recognition from hand and upper-body landmarks. Video never leaves your device; only landmark coordinates are sent.
      </PageHeader>

      {unavailable && (
        <div className="mb-5"><Notice tone="warn" title="Model unavailable: no predictions will be shown">
          No model trained on authentic ISL recordings has been promoted. Camera, hand tracking and quality checks still work so you can verify your setup. {model.data?.reason && <span className="opacity-75">({model.data.reason})</span>}
        </Notice></div>
      )}
      {model.data?.synthetic && <div className="mb-5"><Notice tone="warn" title="Synthetic smoke-test model">{model.data.warning}</Notice></div>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="relative">
            <CameraStage onFrame={onFrame} onState={onState} large />
            {countdown > 0 && <div className="pointer-events-none absolute inset-0 grid place-items-center"><span className="font-display text-8xl font-semibold text-white drop-shadow-[0_4px_24px_rgba(0,0,0,.8)]" aria-live="assertive">{countdown}</span></div>}
            {countdown === -1 && <div className="pointer-events-none absolute right-3 top-3"><Badge tone="bad"><span className="live-dot size-2 rounded-full bg-rose-400" />Capturing…</Badge></div>}
            {countdown === -2 && <div className="pointer-events-none absolute right-3 top-3" role="status"><Badge tone="nova">Classifying…</Badge></div>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {mode === 'capture'
              ? <Button variant="primary" size="lg" icon="record" disabled={!ready || countdown !== 0} onClick={startCapture}>{useCountdown ? 'Capture sign (3-2-1)' : 'Capture sign now'}</Button>
              : <Button variant={running ? 'danger' : 'primary'} size="lg" icon={running ? 'pause' : 'play'} disabled={!ready} onClick={() => setRunning(!running)}>{running ? 'Pause' : 'Start continuous'}</Button>}
            <p className="muted text-sm">{!ready ? (cam.s !== 'live' ? 'Start the camera first.' : 'Waiting for hand tracking…') : mode === 'capture' ? `Sign once after the countdown (${captureSec} s window).` : `Classifying the last ${WINDOW_MS / 1000} s every ${INTERVAL_MS} ms.`}</p>
            {mode === 'capture' && (
              <Select aria-label="Capture length" value={captureSec} onChange={(e) => setCaptureSec(Number(e.target.value))} className="h-9 w-auto py-0 text-sm">
                {CAPTURE_OPTIONS.map((s) => <option key={s} value={s}>{s} s window</option>)}
              </Select>
            )}
            {mode === 'capture' && (
              <label className="flex items-center gap-2 text-sm text-ink-300"><input type="checkbox" className="accent-nova-500" checked={useCountdown} onChange={(e) => setUseCountdown(e.target.checked)} />3-second countdown</label>
            )}
            <Select aria-label="Where recognition runs" value={where} onChange={(e) => setWhere(e.target.value as 'server' | 'device')} className="h-9 w-auto py-0 text-sm">
              <option value="server">{t('On the server')}</option>
              <option value="device">{t('On this device (offline)')}</option>
            </Select>
          </div>
        </div>

        <div className="space-y-4">
          <Card title="Result" action={pred && <StatusBadge status={pred.state} />}>
            {!pred ? (
              <Empty icon="hand" title={unavailable ? 'Model unavailable' : 'No sign captured yet'}>{unavailable ? 'Predictions appear here once a trained model is active.' : 'Start the camera and capture a sign.'}</Empty>
            ) : pred.state === 'recognized' || pred.state === 'uncertain' ? (
              <div className="space-y-4">
                <div>
                  <p className="label">{pred.state === 'recognized' ? 'Recognised sign' : 'Best guess (uncertain)'}</p>
                  <p className="mt-1 font-display text-4xl font-semibold text-fg">{top?.label}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Select aria-label="Meaning language" value={lang} onChange={(e) => setLang(e.target.value as keyof typeof LANGS)} className="h-8 w-auto py-0 text-xs">
                      {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                    {meaning?.text ? <><span className="text-lg text-cyan-200" lang={lang}>{meaning.text}</span><StatusBadge status={meaning.status} /></> : <span className="text-sm italic text-ink-500">No {LANGS[lang]} meaning recorded yet</span>}
                  </div>
                </div>
                {pred.state === 'uncertain' && <p className="text-sm text-amber-200">{pred.reasons[0]}</p>}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" icon="speaker" onClick={() => { const r = speak(meaning?.text || top?.label || '', meaning?.text ? lang : 'en', prefs.speechRate); if (r.reason) toast(r.reason, 'info'); }}>Speak</Button>
                  <Button size="sm" icon="copy" onClick={() => { navigator.clipboard?.writeText(meaning?.text || top?.label || ''); toast('Copied'); }}>Copy</Button>
                  <Button size="sm" icon="bookmark" onClick={save}>Save</Button>
                  <Button size="sm" variant="ghost" icon="flag" onClick={() => setCorrecting(true)}>Wrong?</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <p className="font-medium text-fg">{pred.state === 'unknown' ? 'Not a sign the model knows' : pred.state === 'insufficient_input' ? 'Not enough usable input' : 'Model unavailable'}</p>
                <ul className="list-disc space-y-1 pl-5 text-ink-300">{pred.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                {pred.state === 'insufficient_input' && <p className="muted">Keep both hands in frame, face the camera, and use even lighting.</p>}
              </div>
            )}
            {pred?.quality && (
              <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-ink-700 pt-3 text-center text-xs">
                <div><dt className="text-ink-400">Frames</dt><dd className="tabular-nums text-ink-100">{pred.quality.raw_frames}</dd></div>
                <div><dt className="text-ink-400">Hands visible</dt><dd className="tabular-nums text-ink-100">{Math.round(pred.quality.hand_frame_ratio * 100)}%</dd></div>
                <div><dt className="text-ink-400">Latency</dt><dd className="tabular-nums text-ink-100">{pred.latency_ms ?? '-'} ms</dd></div>
              </dl>
            )}
          </Card>

          {pred && pred.top.length > 0 && (
            <Card title="Top-5 predictions" subtitle={mode === 'continuous' ? 'Smoothed across recent windows' : 'Calibrated class probabilities'}>
              <ProbBars items={(mode === 'continuous' && smoothed.length ? smoothed.map((s) => ({ label: s.label, sub: s.sign_id, p: s.p })) : pred.top.map((t) => ({ label: t.label, sub: t.sign_id, p: t.probability })))} />
            </Card>
          )}

          <Card title="This session" action={session.length > 0 && <Button size="sm" variant="ghost" onClick={() => setSession([])}>Clear</Button>}>
            {session.length === 0 ? <p className="muted text-sm">Results from this session appear here.</p> : (
              <ul className="space-y-2 text-sm">
                {session.map((s, i) => (
                  <li key={i} className="flex items-center justify-between gap-2">
                    <span className="truncate">{s.top[0]?.label ?? '-'}</span>
                    <span className="flex items-center gap-2"><StatusBadge status={s.state} /><span className="text-xs text-ink-500">{new Date(s.at).toLocaleTimeString()}</span></span>
                  </li>
                ))}
              </ul>
            )}
            {user && <Link to="/settings#history" className="mt-3 inline-block text-xs text-nova-300 hover:underline">View saved history</Link>}
          </Card>
        </div>
      </div>
      <CorrectionDialog open={correcting} onClose={() => setCorrecting(false)} pred={pred} />
    </div>
  );
}

function CorrectionDialog({ open, onClose, pred }: { open: boolean; onClose: () => void; pred: Prediction | null }) {
  const { user } = useAuth();
  const [q, setQ] = useState('');
  const { data } = useQuery<{ items: SignSummary[] }>(open && q.length > 1 ? `/signs${qs({ q, size: 8 })}` : null);
  const submit = async (sign?: SignSummary) => {
    const msg = `Live prediction "${pred?.top[0]?.label}" (${pred?.top[0]?.sign_id}, model ${pred?.model_id}) was wrong. ${sign ? `Intended: ${sign.sign_id} ${sign.canonical_sign_name}` : 'Intended sign not in vocabulary.'}`;
    await api('/feedback', { body: { kind: 'prediction', message: msg, sign_id: sign?.sign_id } });
    if (user && pred) await api('/history', { body: { state: pred.state, model_id: pred.model_id, top: pred.top, corrected_sign: sign?.sign_id ?? null } });
    toast('Thank you, the correction was recorded');
    onClose();
  };
  return (
    <Dialog open={open} onClose={onClose} title="Report a wrong prediction">
      <div className="space-y-3">
        <Field label="What did you sign?">{(id) => <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search vocabulary…" />}</Field>
        <ul className="space-y-1">{data?.items.map((s) => <li key={s.sign_id}><button className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-ink-700" onClick={() => submit(s)}>{s.canonical_sign_name}<span className="font-mono text-xs text-ink-500">{s.sign_id}</span></button></li>)}</ul>
        <Button variant="ghost" size="sm" icon="info" onClick={() => submit()}>It isn't in the vocabulary</Button>
      </div>
    </Dialog>
  );
}

export const _icon = Icon;

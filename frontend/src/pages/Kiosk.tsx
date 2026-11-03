// Full-screen kiosk: large touch targets, high contrast, verified quick phrases,
// live recognition, and a one-tap session reset that clears everything.
import { useCallback, useEffect, useRef, useState } from 'react';
import { CameraStage } from '../components/CameraStage';
import { Icon } from '../components/icons';
import { Button, StatusBadge, Toasts } from '../components/ui';
import { api } from '../lib/api';
import type { Frame } from '../lib/features';
import { useQuery } from '../lib/query';
import { navigate } from '../lib/router';
import { speak } from '../lib/speech';
import { prefs, usePrefs } from '../lib/store';
import type { ModelInfo, Prediction } from '../lib/types';

const LANGS = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' } as const;
type Phrase = { id: number; text: string; language: string; is_quick: boolean };

export function KioskPage() {
  const p = usePrefs();
  const [lang, setLang] = useState<keyof typeof LANGS>(p.language);
  const [key, setKey] = useState(0);
  const [pred, setPred] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);
  const frames = useRef<{ f: Frame; a: number }[]>([]);
  const capturing = useRef(false);
  const model = useQuery<ModelInfo>('/model/info');
  const phrases = useQuery<Phrase[]>('/phrases');
  const quick = phrases.data?.filter((x) => x.is_quick && x.language === lang) ?? [];

  useEffect(() => { document.documentElement.classList.add('hc'); return () => { document.documentElement.classList.toggle('hc', prefs.get().highContrast); }; }, []);
  const onFrame = useCallback((f: Frame, a: number) => { if (capturing.current) frames.current.push({ f, a }); }, []);

  const capture = () => {
    frames.current = [];
    capturing.current = true;
    setBusy(true);
    setTimeout(async () => {
      capturing.current = false;
      const w = frames.current;
      try {
        setPred(await api<Prediction>('/predict/sequence', { body: { frames: w.map((x) => x.f), aspect: w[w.length - 1]?.a ?? 4 / 3, top_k: 3 } }));
      } catch (e) { setPred({ state: 'model_unavailable', top: [], reasons: [(e as Error).message] }); }
      setBusy(false);
    }, 2200);
  };
  const reset = () => { setPred(null); frames.current = []; setKey((k) => k + 1); speechSynthesis?.cancel?.(); };
  const top = pred?.top[0];
  const meaning = top?.meanings?.[lang]?.text;

  return (
    <div className="min-h-dvh bg-ink-900 p-4 text-fg md:p-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><img src="/favicon.svg" alt="" className="size-12" /><span className="font-display text-3xl font-semibold">ISL NOVA</span></div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Language">
          {Object.entries(LANGS).map(([k, v]) => <Button key={k} size="lg" variant={lang === k ? 'signal' : 'secondary'} onClick={() => setLang(k as keyof typeof LANGS)} aria-pressed={lang === k}>{v}</Button>)}
          <Button size="lg" variant="danger" icon="refresh" onClick={reset}>New session</Button>
          <Button size="lg" variant="ghost" icon="close" onClick={() => navigate('/')} aria-label="Exit kiosk" />
        </div>
      </header>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <CameraStage key={key} onFrame={onFrame} large />
          <Button size="lg" variant="primary" className="h-20 w-full text-2xl" icon="hand" loading={busy} disabled={!model.data?.available} onClick={capture}>
            {model.data?.available ? (busy ? 'Watching your sign…' : 'Tap, then sign') : 'Recognition unavailable'}
          </Button>
        </div>
        <div className="space-y-4">
          <section className="rounded-3xl border-2 border-fg p-6" aria-live="polite">
            {!model.data?.available ? <p className="text-2xl">Sign recognition is not available on this kiosk yet. Please use the phrases below.</p>
              : !pred ? <p className="text-2xl text-ink-200">Your result will appear here.</p>
              : <>
                  <StatusBadge status={pred.state} />
                  {top && (pred.state === 'recognized' || pred.state === 'uncertain')
                    ? <><p className="mt-3 font-display text-6xl font-semibold">{meaning || top.label}</p>
                        <Button size="lg" variant="signal" className="mt-5" icon="speaker" onClick={() => speak(meaning || top.label, meaning ? lang : 'en', p.speechRate)}>Speak</Button></>
                    : <p className="mt-3 text-2xl">{pred.state === 'unknown' ? 'Sorry, that sign was not recognised. Please try again.' : 'Please keep your hands in view and try again.'}</p>}
                </>}
          </section>
          <section>
            <h2 className="mb-3 text-xl font-semibold">Quick phrases</h2>
            {!quick.length ? <p className="text-lg text-ink-200">No verified quick phrases for {LANGS[lang]} yet.</p> : (
              <div className="grid gap-3 sm:grid-cols-2">
                {quick.map((q) => <button key={q.id} onClick={() => speak(q.text, q.language, p.speechRate)} className="flex min-h-20 items-center gap-3 rounded-2xl border-2 border-fg px-5 text-left text-2xl hover:bg-fg hover:text-ink-900" lang={q.language}><Icon name="speaker" size={28} />{q.text}</button>)}
              </div>
            )}
          </section>
        </div>
      </div>
      <Toasts />
    </div>
  );
}

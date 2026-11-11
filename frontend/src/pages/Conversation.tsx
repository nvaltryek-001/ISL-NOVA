// Two-way conversation: the signer signs (recognised word by word, spoken aloud);
// the speaker talks (speech-to-text where the browser supports it) and sees matching signs.
import { useCallback, useEffect, useRef, useState } from 'react';
import { CameraStage } from '../components/CameraStage';
import { SignAnimation } from '../components/SignAnimation';
import { Icon } from '../components/icons';
import { Badge, Button, Card, PageHeader, Select } from '../components/ui';
import { LANG_NAMES, type Lang, SPEECH_LANG, useT } from '../i18n';
import { api } from '../lib/api';
import { type Frame, windowQuality } from '../lib/features';
import { type Segment, SignSegmenter } from '../lib/segmenter';
import { speak } from '../lib/speech';
import { usePrefs } from '../lib/store';
import { type Match, textToSigns } from '../lib/textToSign';

type Pred = { state: string; top: { sign_id: string; label: string; probability: number; meanings?: Record<string, { text: string; status: string }> }[] };
type Line = { who: 'signer' | 'speaker'; text: string; draft?: boolean };

const WINDOW_MS = 2000;
const INTERVAL_MS = 900;

// minimal typing for the Web Speech API recogniser
type Rec = { lang: string; continuous: boolean; interimResults: boolean; start: () => void; stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null; onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null };
const RecCtor = (globalThis as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec }).SpeechRecognition
  ?? (globalThis as unknown as { webkitSpeechRecognition?: new () => Rec }).webkitSpeechRecognition;

export function ConversationPage() {
  const t = useT();
  const p = usePrefs();
  const [lang, setLang] = useState<Lang>(p.language);
  const [lines, setLines] = useState<Line[]>([]);
  const [signing, setSigning] = useState(false);
  const [listening, setListening] = useState(false);
  const [signs, setSigns] = useState<Match[]>([]);
  const buffer = useRef<{ f: Frame; t: number }[]>([]);
  const last = useRef<{ id: string; at: number } | null>(null);
  const rec = useRef<Rec | null>(null);
  const [aspect, setAspect] = useState(4 / 3);
  const [mode, setMode] = useState<'pauses' | 'window'>('pauses');
  const seg = useRef(new SignSegmenter());
  const segments = useRef<Segment[]>([]);
  const [sequence, setSequence] = useState<string[]>([]);

  const onFrame = useCallback((f: Frame, a: number, now: number) => {
    buffer.current.push({ f, t: now });
    while (buffer.current.length && now - buffer.current[0].t > 4000) buffer.current.shift();
    const done = seg.current.push(f, now);
    if (done) segments.current.push(done);
    setAspect(a);
  }, []);

  const accept = useCallback((r: Pred, at: number, repeatMs: number) => {
    const top = r.top[0];
    if (r.state !== 'recognized' || !top || (last.current?.id === top.sign_id && at - last.current.at < repeatMs)) return;
    last.current = { id: top.sign_id, at };
    const m = top.meanings?.[lang];
    const text = m?.text || top.label;
    setLines((l) => [...l, { who: 'signer', text, draft: m ? m.status !== 'verified' : lang !== 'en' }]);
    setSequence((q) => [...q, text]);
    speak(text, lang, p.speechRate);
  }, [lang, p.speechRate]);

  // signer side: either one prediction per segment split at pauses (default), or a sliding window
  useEffect(() => {
    if (!signing) return;
    seg.current.reset();
    segments.current = [];
    let busy = false;
    const iv = setInterval(async () => {
      if (busy) return;
      if (mode === 'pauses') {
        const s = segments.current.shift();
        if (!s || s.frames.length < 8) return;
        busy = true;
        try {
          const r = await api<Pred>('/predict/sequence', { body: { frames: s.frames.map((x) => x.f), aspect, top_k: 3 } });
          accept(r, s.end, 1500);
        } catch { /* network hiccup: drop this segment */ } finally { busy = false; }
        return;
      }
      const end = performance.now();
      const w = buffer.current.filter((x) => end - x.t <= WINDOW_MS);
      if (w.length < 8 || windowQuality(w.map((x) => x.f)).hands < 0.4) return;
      busy = true;
      try {
        accept(await api<Pred>('/predict/sequence', { body: { frames: w.map((x) => x.f), aspect, top_k: 3 } }), end, 4000);
      } catch { /* network hiccup: next window */ } finally { busy = false; }
    }, mode === 'pauses' ? 250 : INTERVAL_MS);
    return () => clearInterval(iv);
  }, [signing, mode, aspect, accept]);

  // speaker side: browser speech recognition
  const toggleListen = () => {
    if (!RecCtor) return;
    if (listening) { rec.current?.stop(); setListening(false); return; }
    const r = new RecCtor();
    r.lang = SPEECH_LANG[lang]; r.continuous = true; r.interimResults = false;
    r.onresult = async (e) => {
      const res = e.results[e.results.length - 1];
      if (!res.isFinal) return;
      const text = res[0].transcript.trim();
      if (!text) return;
      setLines((l) => [...l, { who: 'speaker', text }]);
      setSigns((await textToSigns(text)).filter((m) => m.sign_id));
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r; r.start(); setListening(true);
  };
  useEffect(() => () => rec.current?.stop(), []);

  return (
    <div>
      <PageHeader title="Conversation"
        actions={<Select aria-label={t('Output language')} value={lang} onChange={(e) => setLang(e.target.value as Lang)} className="w-auto">
          {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l}>{LANG_NAMES[l]}</option>)}
        </Select>}>
        {t('The signer signs one word at a time; recognised signs appear as text and are spoken. The speaker talks; their words appear as text with matching signs.')}
      </PageHeader>
      <p className="-mt-2 mb-5 flex items-center gap-1.5 text-xs text-ink-400"><Icon name="info" size={14} />{t('Word-by-word assistance, not interpretation')}. {t('For important conversations, use a qualified ISL interpreter.')}</p>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Signer" action={<div className="flex flex-wrap items-center gap-2">
            <Select aria-label={t('How signs are separated')} value={mode} onChange={(e) => setMode(e.target.value as 'pauses' | 'window')} className="w-auto">
              <option value="pauses">{t('Split at pauses')}</option><option value="window">{t('Sliding window')}</option>
            </Select>
            <Button variant={signing ? 'danger' : 'primary'} icon={signing ? 'pause' : 'play'} onClick={() => setSigning(!signing)}>{signing ? 'Pause' : 'Start signing'}</Button></div>}>
          <CameraStage onFrame={onFrame} large />
          <div className="mt-3">
            <p className="label mb-1">{t('Recognized word sequence')}</p>
            <p className="min-h-8 text-xl text-fg" lang={lang} data-testid="word-sequence">{sequence.join(' · ') || <span className="muted text-base">{t('Pause briefly between signs.')}</span>}</p>
            <p className="muted text-xs">{t('Signs recognised one by one, in order. This is not a translation: ISL grammar is not modelled.')}</p>
            {sequence.length > 0 && <Button size="sm" variant="ghost" onClick={() => setSequence([])}>Clear</Button>}
          </div>
        </Card>
        <Card title="Speaker" action={RecCtor
          ? <Button variant={listening ? 'danger' : 'primary'} icon="mic" onClick={toggleListen}>{listening ? 'Stop listening' : 'Start listening'}</Button>
          : <Badge tone="warn">{t('Speech recognition not supported in this browser')}</Badge>}>
          {signs.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {signs.slice(0, 4).map((m, i) => <div key={i}><p className="mb-1 text-lg font-medium text-fg">{m.text}</p><SignAnimation signId={m.sign_id!} size="sm" /></div>)}
            </div>
          ) : <p className="muted py-10 text-center text-lg">{t('Spoken words with a matching sign are shown here.')}</p>}
        </Card>
      </div>
      <Card className="mt-5" title="Transcript" action={lines.length > 0 && <Button size="sm" onClick={() => setLines([])}>Clear</Button>}>
        <ol className="space-y-2" aria-live="polite">
          {lines.length === 0 && <li className="muted text-lg">{t('The conversation will appear here.')}</li>}
          {lines.map((l, i) => (
            <li key={i} className={`flex items-baseline gap-3 text-2xl ${l.who === 'signer' ? 'text-nova-300' : 'text-fg'}`} lang={l.who === 'signer' ? lang : undefined}>
              <Badge tone={l.who === 'signer' ? 'nova' : 'signal'}>{t(l.who === 'signer' ? 'Signer' : 'Speaker')}</Badge>
              <span>{l.text}</span>{l.draft && <Badge tone="warn">{t('Draft')}</Badge>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

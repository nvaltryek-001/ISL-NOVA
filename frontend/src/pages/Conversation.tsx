// Two-way conversation: the signer signs (recognised word by word, spoken aloud);
// the speaker talks (speech-to-text where the browser supports it) and sees matching signs.
import { useCallback, useEffect, useRef, useState } from 'react';
import { CameraStage } from '../components/CameraStage';
import { SignAnimation } from '../components/SignAnimation';
import { Badge, Button, Card, Notice, PageHeader, Select } from '../components/ui';
import { LANG_NAMES, type Lang, SPEECH_LANG, useT } from '../i18n';
import { api } from '../lib/api';
import { type Frame, windowQuality } from '../lib/features';
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

  const onFrame = useCallback((f: Frame, a: number, now: number) => {
    buffer.current.push({ f, t: now });
    while (buffer.current.length && now - buffer.current[0].t > 4000) buffer.current.shift();
    setAspect(a);
  }, []);

  // signer side: classify a sliding window; accept only confident, non-repeated signs
  useEffect(() => {
    if (!signing) return;
    let busy = false;
    const iv = setInterval(async () => {
      if (busy) return;
      const end = performance.now();
      const w = buffer.current.filter((x) => end - x.t <= WINDOW_MS);
      if (w.length < 8 || windowQuality(w.map((x) => x.f)).hands < 0.4) return;
      busy = true;
      try {
        const r = await api<Pred>('/predict/sequence', { body: { frames: w.map((x) => x.f), aspect, top_k: 3 } });
        const top = r.top[0];
        if (r.state === 'recognized' && top && !(last.current?.id === top.sign_id && end - last.current.at < 4000)) {
          last.current = { id: top.sign_id, at: end };
          const m = top.meanings?.[lang];
          const text = m?.text || top.label;
          setLines((l) => [...l, { who: 'signer', text, draft: m ? m.status !== 'verified' : lang !== 'en' }]);
          speak(text, lang, p.speechRate);
        }
      } catch { /* network hiccup: next window */ } finally { busy = false; }
    }, INTERVAL_MS);
    return () => clearInterval(iv);
  }, [signing, lang, aspect, p.speechRate]);

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
      <PageHeader kicker="NOVA Conversation" title="Conversation"
        actions={<Select aria-label={t('Output language')} value={lang} onChange={(e) => setLang(e.target.value as Lang)} className="w-auto">
          {(Object.keys(LANG_NAMES) as Lang[]).map((l) => <option key={l} value={l}>{LANG_NAMES[l]}</option>)}
        </Select>}>
        {t('The signer signs one word at a time; recognised signs appear as text and are spoken. The speaker talks; their words appear as text with matching signs.')}
      </PageHeader>
      <div className="mb-5"><Notice tone="warn" title="Word-by-word assistance, not interpretation">{t('Recognition is isolated-sign only and can be wrong. Hindi and Kannada meanings are drafts. For important conversations, use a qualified ISL interpreter.')}</Notice></div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Signer" action={<Button variant={signing ? 'danger' : 'primary'} icon={signing ? 'pause' : 'play'} onClick={() => setSigning(!signing)}>{signing ? 'Pause' : 'Start signing'}</Button>}>
          <CameraStage onFrame={onFrame} large />
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

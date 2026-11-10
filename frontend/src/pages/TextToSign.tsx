// Text -> Sign viewer: type English, Hindi or Kannada; see each matched vocabulary sign animated.
import { useState } from 'react';
import { SignAnimation } from '../components/SignAnimation';
import { Badge, Button, Card, Empty, Notice, PageHeader, Textarea } from '../components/ui';
import { useT } from '../i18n';
import { type Match, textToSigns } from '../lib/textToSign';

export function TextToSignPage() {
  const t = useT();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [current, setCurrent] = useState(0);

  const run = async () => {
    setBusy(true);
    try { setMatches(await textToSigns(text)); setCurrent(0); } finally { setBusy(false); }
  };
  const signs = (matches ?? []).filter((m) => m.sign_id);
  const cur = signs[current];

  return (
    <div>
      <PageHeader kicker="NOVA Text to Sign" title="Text to Sign">
        {t('Type words in English, Hindi or Kannada to see the matching signs from the 200-sign vocabulary.')}
      </PageHeader>
      <div className="mb-5"><Notice tone="warn" title="A sequence of signs, not an ISL translation">{t('ISL has its own grammar and word order. This tool shows individual vocabulary signs for the words it recognises; it does not translate sentences.')}</Notice></div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card title="Text">
          <Textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} className="text-lg" aria-label={t('Text')}
            placeholder={t('e.g. good morning teacher · नमस्ते दोस्त · ನಮಸ್ಕಾರ ಸ್ನೇಹಿತ')} />
          <Button className="mt-3" variant="primary" icon="play" loading={busy} disabled={!text.trim()} onClick={run}>Show signs</Button>
          {matches && (
            <div className="mt-4 flex flex-wrap gap-2" aria-label={t('Matched words')}>
              {matches.map((m, i) => m.sign_id
                ? <button key={i} onClick={() => setCurrent(signs.indexOf(m))} className={`rounded-lg border px-2.5 py-1.5 text-sm ${cur === m ? 'border-nova-400 bg-nova-500/10' : 'border-ink-700'}`}>{m.text} <span className="text-xs text-ink-400">{m.sign_id}</span></button>
                : <Badge key={i}>{m.text}: {t('no sign in vocabulary')}</Badge>)}
            </div>
          )}
        </Card>
        <Card title={cur ? `${cur.text} · ${cur.label}` : 'Sign'} action={signs.length > 1 && (
          <div className="flex gap-2">
            <Button size="sm" disabled={current === 0} onClick={() => setCurrent(current - 1)}>Previous</Button>
            <Button size="sm" disabled={current >= signs.length - 1} onClick={() => setCurrent(current + 1)}>Next</Button>
          </div>)}>
          {cur?.sign_id ? <SignAnimation signId={cur.sign_id} size="lg" /> : <Empty icon="hand" title={matches ? 'No vocabulary sign matched' : 'Type some text to begin'} />}
        </Card>
      </div>
    </div>
  );
}

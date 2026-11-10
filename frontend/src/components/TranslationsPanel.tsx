// Three-language meaning coverage, with review-sheet export/import for linguists and admins.
import { useRef, useState } from 'react';
import { LANG_NAMES, type Lang, useT } from '../i18n';
import { useQuery } from '../lib/query';
import { auth, can, toast, useAuth } from '../lib/store';
import { Badge, Button, Card } from './ui';

type Cov = { signs: number; languages: Record<Lang, Record<string, number>> };

export function TranslationsPanel() {
  const t = useT();
  const { user } = useAuth();
  const { data, refetch } = useQuery<Cov>('/translations/coverage');
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  if (!data) return null;
  const editor = can(user, 'translations:write');

  const download = async () => {
    const r = await fetch('/api/v1/translations/review-sheet.csv', { headers: { Authorization: `Bearer ${auth.get().token}` } });
    if (!r.ok) { toast('Could not export the translation sheet', 'error'); return; }
    const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'isl-nova-translations-review.csv'; a.click();
  };
  const upload = async (f: File) => {
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('file', f);
      const r = await fetch('/api/v1/translations/import', { method: 'POST', body: fd, headers: { Authorization: `Bearer ${auth.get().token}` } });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.error?.message ?? 'Import failed');
      toast(`${j.applied} meanings updated${j.errors.length ? `, ${j.errors.length} rows rejected` : ''}`, j.errors.length ? 'error' : 'ok');
      refetch();
    } catch (e) { toast((e as Error).message, 'error'); } finally { setBusy(false); if (file.current) file.current.value = ''; }
  };

  return (
    <Card title="Translation coverage" subtitle={`${data.signs} signs · English, हिन्दी, ಕನ್ನಡ`}
      action={editor && <div className="flex flex-wrap gap-2">
        <Button size="sm" icon="download" onClick={download}>Review sheet (CSV)</Button>
        <Button size="sm" icon="upload" loading={busy} onClick={() => file.current?.click()}>Import reviewed sheet</Button>
        <input ref={file} type="file" accept=".csv,text/csv" className="hidden" aria-label={t('Import reviewed sheet')}
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      </div>}>
      <div className="grid gap-3 sm:grid-cols-3">
        {(['en', 'hi', 'kn'] as Lang[]).map((l) => {
          const c = data.languages[l] ?? {};
          return (
            <div key={l} className="rounded-xl border border-ink-700 p-3" lang={l}>
              <p className="text-lg font-semibold text-fg">{LANG_NAMES[l]}</p>
              <p className="muted text-xs">{c.with_text ?? 0} / {data.signs} {t('Meanings').toLowerCase()}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge tone="ok">{t('Verified')} {c.verified ?? 0}</Badge>
                {!!c.draft && <Badge tone="warn">{t('Draft')} {c.draft}</Badge>}
                {!!c.source_gloss && <Badge tone="signal">{t('Source gloss')} {c.source_gloss}</Badge>}
                {!!c.pending && <Badge>{t('Pending')} {c.pending}</Badge>}
              </div>
            </div>
          );
        })}
      </div>
      <p className="muted mt-3 text-xs">Hindi and Kannada meanings are machine drafts until a native speaker reviews them and a linguist verifies them. Drafts are always labelled.</p>
    </Card>
  );
}

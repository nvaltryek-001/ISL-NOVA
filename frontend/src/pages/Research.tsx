import { Badge, Card, PageHeader } from '../components/ui';
import { useT } from '../i18n';
import { useQuery } from '../lib/query';
import type { ModelInfo } from '../lib/types';

const REPO = 'https://github.com/nvaltryek-001/ISL-NOVA/blob/main';

// Recorded runs on the INCLUDE official test split (635 sequences, 200 classes); source: research/RESULTS.md
const RESULTS: { model: string; top1: string; top5: string; f1: string; note?: string }[] = [
  { model: 'BiLSTM-attention (v3, active)', top1: '95.1 %', top5: '99.4 %', f1: '94.1 %', note: 'v3' },
  { model: 'LSTM + frame-rate augmentation (v2)', top1: '92.0 %', top5: '98.7 %', f1: '91.6 %' },
  { model: 'LSTM baseline (v1)', top1: '91.7 %', top5: '98.3 %', f1: '91.7 %' },
  { model: 'Pooled logistic regression', top1: '89.1 %', top5: '98.3 %', f1: '88.8 %' },
  { model: 'GRU', top1: '86.5 %', top5: '97.6 %', f1: '86.1 %' },
  { model: 'DTW 1-nearest-neighbour', top1: '84.4 %', top5: '94.6 %', f1: '83.5 %' },
];

const OTHER: [string, string][] = [
  ['Unknown signs accepted (v3, reserve glosses part B)', '8.8 %'],
  ['Known signs held back (v3, part B)', '13.2 %'],
  ['Browser pipeline, 73 held-out clips as a webcam', '84.9 %'],
  ['Face features (v4), BiLSTM-attention, 3-seed mean', '95.8 % vs 94.5 %'],
];

const QUESTIONS = [
  ['RQ1', 'How well do landmark-only temporal models recognise isolated ISL signs?'],
  ['RQ2', 'Which feature blocks (hand shape, two-hand relations, trajectories, velocities, face) contribute most?'],
  ['RQ3', 'How reliably can a calibrated classifier reject signs outside its vocabulary?'],
  ['RQ4', 'How does performance vary with lighting, camera distance and signing speed?'],
];

const DOCS = [
  ['Results', 'research/RESULTS.md'], ['v3 models', 'research/V3_MODELS.md'], ['Face features (v4)', 'research/V4_FACE_FEATURES.md'],
  ['Frame-rate robustness', 'research/FPS_ROBUSTNESS.md'], ['Open-set evaluation', 'research/OPEN_SET_V2.md'], ['Literature review', 'research/LITERATURE_REVIEW.md'],
  ['Experiment protocol', 'research/EXPERIMENT_PROTOCOL.md'], ['Limitations', 'research/LIMITATIONS.md'], ['References (BibTeX)', 'research/REFERENCES.bib'],
];

const REFS = [
  { key: 'INCLUDE', cite: 'Sridhar, Ganesan, Kumar, Khapra. INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition. ACM Multimedia 2020.', doi: '10.1145/3394171.3413528' },
  { key: 'iSign', cite: 'Joshi, Mohanty, Kanakanti, Mangla, Choudhary, Barbate, Modi. iSign: A Benchmark for Indian Sign Language Processing. Findings of ACL 2024.', doi: '10.18653/v1/2024.findings-acl.643' },
];

export function ResearchPage() {
  const t = useT();
  const m = useQuery<ModelInfo>('/model/info');
  const live = m.data?.available && !m.data.synthetic ? m.data.metrics_summary : undefined;
  return (
    <div className="space-y-5">
      <PageHeader title="Research Centre">
        {t('Results, research questions and protocols behind ISL NOVA.')}
      </PageHeader>

      <Card title="Benchmark results" subtitle={t('INCLUDE official test split · 635 sequences · 200 signs')}>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t('Benchmark results')}>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-ink-400">
              <tr><th className="py-2 pr-4 font-medium">{t('Model')}</th><th className="px-3 py-2 text-right font-medium">Top-1</th><th className="px-3 py-2 text-right font-medium">Top-5</th><th className="py-2 pl-3 text-right font-medium">Macro-F1</th></tr>
            </thead>
            <tbody className="stagger divide-y divide-ink-700/70">
              {RESULTS.map((r) => (
                <tr key={r.model} className={r.note ? 'font-medium text-fg' : 'text-ink-200'}>
                  <td className="py-2.5 pr-4">{r.model}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{r.top1}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{r.top5}</td>
                  <td className="py-2.5 pl-3 text-right tabular-nums">{r.f1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {live && <p className="muted mt-3 text-xs">{t('Active model, read live')}: top-1 {(live.test_top1 * 100).toFixed(1)} %, macro-F1 {(live.test_macro_f1 * 100).toFixed(1)} %</p>}
        <p className="muted mt-1 text-xs">{t('INCLUDE does not identify signers, so these results are not signer-independent.')}</p>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="More measurements">
          <dl className="stagger space-y-3 text-sm">
            {OTHER.map(([k, v]) => <div key={k} className="flex items-start justify-between gap-3"><dt className="text-ink-300">{k}</dt><dd className="shrink-0 font-medium tabular-nums text-fg">{v}</dd></div>)}
          </dl>
        </Card>
        <Card className="xl:col-span-2" title="Research questions">
          <ul className="space-y-3">{QUESTIONS.map(([k, q]) => <li key={k} className="flex gap-3"><Badge tone="nova">{k}</Badge><span className="text-ink-200">{q}</span></li>)}</ul>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Documents" subtitle="Versioned in the repository">
          <ul className="grid gap-1.5 sm:grid-cols-2">{DOCS.map(([d, p]) => <li key={p}><a className="lift block rounded-lg border border-ink-700 px-3 py-2 text-sm hover:text-fg" href={`${REPO}/${p}`} target="_blank" rel="noreferrer noopener">{d}</a></li>)}</ul>
        </Card>
        <Card title="Key references">
          <ul className="space-y-3 text-sm">{REFS.map((r) => <li key={r.key}><p className="text-ink-200">{r.cite}</p><a className="text-xs text-nova-300 hover:underline" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer noopener">doi:{r.doi}</a></li>)}</ul>
        </Card>
      </div>
    </div>
  );
}

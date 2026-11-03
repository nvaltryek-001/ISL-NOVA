import { Badge, Card, PageHeader, StatusBadge } from '../components/ui';
import { useQuery } from '../lib/query';
import type { DatasetStats, ModelInfo } from '../lib/types';

const REPO = 'https://github.com/nvaltryek-001/ISL-NOVA/blob/feat/isl-nova-platform';

const QUESTIONS = [
  ['RQ1', 'How well do landmark-only temporal models recognise isolated ISL signs from signers never seen in training?'],
  ['RQ2', 'Which feature blocks (hand shape, two-hand relations, body-relative trajectories, velocities) contribute most under a signer-independent protocol?'],
  ['RQ3', 'How reliably can a calibrated classifier reject signs outside its vocabulary (open-set rejection)?'],
  ['RQ4', 'How does performance vary with lighting, camera distance and signing speed?'],
];

const DOCS = [
  ['Literature review', 'research/LITERATURE_REVIEW.md'], ['Research questions', 'research/RESEARCH_QUESTIONS.md'],
  ['Dataset methodology', 'research/DATASET_METHODOLOGY.md'], ['Experiment protocol', 'research/EXPERIMENT_PROTOCOL.md'],
  ['Signer-independent protocol', 'research/SIGNER_INDEPENDENT_PROTOCOL.md'], ['Open-set evaluation', 'research/OPEN_SET_EVALUATION.md'],
  ['Ablation study plan', 'research/ABLATION_STUDY.md'], ['Results template', 'research/RESULTS_TEMPLATE.md'],
  ['Paper outline', 'research/PAPER_OUTLINE.md'], ['Limitations', 'research/LIMITATIONS.md'], ['References (BibTeX)', 'research/REFERENCES.bib'],
];

const REFS = [
  { key: 'INCLUDE', cite: 'Sridhar, Ganesan, Kumar, Khapra. INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition. ACM Multimedia 2020.', doi: '10.1145/3394171.3413528' },
  { key: 'iSign', cite: 'Joshi, Mohanty, Kanakanti, Mangla, Choudhary, Barbate, Modi. iSign: A Benchmark for Indian Sign Language Processing. Findings of ACL 2024.', doi: '10.18653/v1/2024.findings-acl.643' },
];

export function ResearchPage() {
  const ds = useQuery<DatasetStats>('/dataset/stats');
  const m = useQuery<ModelInfo>('/model/info');
  const results = m.data?.available && !m.data.synthetic;
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Research Centre" title="Research Centre">
        Research questions, protocols and the status of each experiment. Results sections stay empty until experiments on authentic data have been run.
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Research questions">
          <ul className="space-y-3">{QUESTIONS.map(([k, q]) => <li key={k} className="flex gap-3"><Badge tone="nova">{k}</Badge><span className="text-ink-200">{q}</span></li>)}</ul>
        </Card>
        <Card title="Evidence status">
          <ul className="space-y-3 text-sm">
            <li className="flex justify-between"><span>Vocabulary (200 slots)</span><StatusBadge status="completed" /></li>
            <li className="flex justify-between"><span>Feature contract + parity tests</span><StatusBadge status="completed" /></li>
            <li className="flex justify-between"><span>Training pipeline (smoke-tested)</span><StatusBadge status="completed" /></li>
            <li className="flex justify-between"><span>Authentic training data</span><StatusBadge status={(ds.data?.approved_samples ?? 0) > 0 ? 'collecting' : 'blocked'} /></li>
            <li className="flex justify-between"><span>Signer-independent results</span><StatusBadge status={results ? 'succeeded' : 'pending'} /></li>
            <li className="flex justify-between"><span>Ablations</span><StatusBadge status="pending" /></li>
          </ul>
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Protocol documents" subtitle="Versioned in the repository">
          <ul className="grid gap-1.5 sm:grid-cols-2">{DOCS.map(([t, p]) => <li key={p}><a className="block rounded-lg border border-ink-700 px-3 py-2 text-sm hover:border-nova-400 hover:text-fg" href={`${REPO}/${p}`} target="_blank" rel="noreferrer noopener">{t}</a></li>)}</ul>
        </Card>
        <Card title="Key references" subtitle="Verified bibliographic records">
          <ul className="space-y-3 text-sm">{REFS.map((r) => <li key={r.key}><p className="text-ink-200">{r.cite}</p><a className="text-xs text-nova-300 hover:underline" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer noopener">doi:{r.doi}</a></li>)}</ul>
        </Card>
      </div>
      <Card title="Benchmark results" subtitle="Signer-independent, held-out test split">
        {results ? <p className="text-sm text-ink-200">A model is active; see the AI Laboratory for its held-out metrics and per-class report.</p>
          : <p className="text-sm text-ink-300">No results. No model has been trained on authentic ISL recordings in this deployment, so this table is intentionally empty.</p>}
      </Card>
    </div>
  );
}

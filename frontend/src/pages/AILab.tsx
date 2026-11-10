import { useState } from 'react';
import { RequireAuth } from '../App';
import { Heatmap, HBars } from '../components/charts';
import { Badge, Button, Card, Dialog, Empty, ErrorNote, Field, Input, Loading, Notice, PageHeader, Select, StatusBadge, Table, Tabs, fmt } from '../components/ui';
import { api } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { can, toast, useAuth } from '../lib/store';
import type { ModelInfo } from '../lib/types';

type Tab = 'model' | 'evaluation' | 'newsigners' | 'registry' | 'experiments' | 'contract';

export function AILabPage() {
  const [tab, setTab] = useState<Tab>('model');
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA AI Laboratory" title="AI Laboratory"
        actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'model', label: 'Active model' }, { id: 'evaluation', label: 'Evaluation' }, { id: 'newsigners', label: 'New signers' }, { id: 'registry', label: 'Registry' }, { id: 'experiments', label: 'Experiments' }, { id: 'contract', label: 'Feature contract' }]} />}>
        Models, experiments and held-out evaluation. Metrics shown here are read from the artefacts written by the training pipeline. None are typed in by hand.
      </PageHeader>
      {tab === 'model' && <ActiveModel />}
      {tab === 'evaluation' && <Evaluation />}
      {tab === 'newsigners' && <RequireAuth perm="experiments:read"><NewSigners /></RequireAuth>}
      {tab === 'registry' && <RequireAuth perm="experiments:read"><Registry /></RequireAuth>}
      {tab === 'experiments' && <RequireAuth perm="experiments:read"><Experiments /></RequireAuth>}
      {tab === 'contract' && <Contract />}
    </div>
  );
}

function ActiveModel() {
  const { data: m } = useQuery<ModelInfo>('/model/info');
  const metrics = useQuery<any>('/model/metrics');
  if (!m) return <Loading />;
  if (!m.available) return (
    <Card>
      <Empty icon="cpu" title="No model is serving predictions">
        <p>{m.reason}</p>
        <p className="mt-2">To train one: import or record authentic ISL data, approve it, freeze a dataset version, then run an experiment and promote the resulting model after reviewing its held-out metrics.</p>
      </Empty>
    </Card>
  );
  const t = metrics.data?.test;
  return (
    <div className="space-y-4">
      {m.synthetic && <Notice tone="warn" title="Synthetic smoke-test model">{m.warning}</Notice>}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Model" className="xl:col-span-1">
          <dl className="space-y-2 text-sm">
            {[['ID', <code key="id" className="text-xs">{m.model_id}</code>], ['Architecture', m.kind], ['Classes', m.n_classes], ['Contract', m.feature_contract.name], ['Reject threshold τ', m.thresholds?.tau.toFixed(3)], ['Temperature', m.thresholds?.temperature.toFixed(3)], ['Dataset version', String(m.lineage?.dataset_version ?? '-')]].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between gap-3"><dt className="text-ink-400">{k}</dt><dd className="text-right">{v}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title="Held-out test metrics" className="xl:col-span-2" subtitle="Evaluated once, after model selection on the validation split">
          {!t ? <Loading /> : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[['Top-1', fmt.pct(t.top1)], ['Top-5', fmt.pct(t.top5)], ['Macro-F1', fmt.pct(t.macro_f1)], ['Weighted-F1', fmt.pct(t.weighted_f1)], ['ECE', t.ece?.toFixed(3)], ['Test samples', t.n], ['Latency / sample', `${metrics.data.latency_ms_per_sample_batch} ms`], ['Model size', fmt.bytes(metrics.data.model_size_bytes)]].map(([k, v]) => (
                <div key={String(k)} className="rounded-xl bg-ink-800 p-3"><p className="label">{k}</p><p className="mt-1 font-display text-2xl font-semibold text-fg">{v}</p></div>
              ))}
            </div>
          )}
          {metrics.data?.open_set && (
            <div className="mt-4 rounded-xl border border-ink-700 p-3 text-sm">
              <p className="label mb-2">Unknown-sign rejection (open set)</p>
              <p className="text-ink-300">Known accepted {fmt.pct(metrics.data.open_set.known_accept_rate)} · unknown rejected {fmt.pct(metrics.data.open_set.unknown_reject_rate)} · AUROC {metrics.data.open_set.auroc_maxprob?.toFixed(3)} · n unknown = {metrics.data.open_set.n_unknown}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Evaluation() {
  const ev = useQuery<{ available: boolean; per_class: any[]; synthetic?: boolean }>('/evaluation/metrics');
  const cm = useQuery<{ available: boolean; labels: string[]; matrix: number[][] }>('/evaluation/confusion-matrix');
  if (!ev.data) return <Loading />;
  if (!ev.data.available) return <Card><Empty icon="layers" title="No evaluation results exist">Evaluation results appear after a trained model is promoted.</Empty></Card>;
  const worst = [...ev.data.per_class].filter((c) => c.support > 0).sort((a, b) => a.f1 - b.f1).slice(0, 12);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {ev.data.synthetic && <div className="xl:col-span-2"><Notice tone="warn" title="These metrics come from a synthetic smoke-test model and are not ISL results" /></div>}
      <Card title="Lowest per-class F1" subtitle="Where the model struggles most"><HBars label="Per-class F1" max={1} data={worst.map((c) => ({ label: `${c.label} (${c.support})`, value: Number(c.f1.toFixed(2)) }))} /></Card>
      <Card title="Confusion matrix">{cm.data?.available && <Heatmap matrix={cm.data.matrix} labels={cm.data.labels} label="Test confusion matrix" />}</Card>
      <Card className="xl:col-span-2" title="Per-class report">
        <Table head={['Class', 'Precision', 'Recall', 'F1', 'Support']} className="max-h-96">
          {ev.data.per_class.map((c) => <tr key={c.class}><td className="px-3 py-2">{c.label} <span className="font-mono text-xs text-ink-500">{c.sign_id}</span></td><td className="px-3 py-2 tabular-nums">{fmt.pct(c.precision)}</td><td className="px-3 py-2 tabular-nums">{fmt.pct(c.recall)}</td><td className="px-3 py-2 tabular-nums">{fmt.pct(c.f1)}</td><td className="px-3 py-2 tabular-nums">{c.support}</td></tr>)}
        </Table>
      </Card>
    </div>
  );
}

function Registry() {
  const { user } = useAuth();
  const { data, error } = useQuery<{ active: string | null; models: any[]; history: any[] }>('/models');
  const inv = ['/models', '/model', '/evaluation', '/dashboard'];
  const promote = useMutation((id: string) => api(`/models/${encodeURIComponent(id)}/promote`, { method: 'POST' }), { invalidates: inv, onSuccess: () => toast('Model promoted to production') });
  const rollback = useMutation(() => api('/models/rollback', { method: 'POST' }), { invalidates: inv, onSuccess: () => toast('Rolled back') });
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  return (
    <Card title="Model registry" subtitle="Synthetic smoke-test models can never be promoted in production"
      action={can(user, 'models:promote') && data.history.length > 0 && <Button icon="undo" onClick={() => rollback.mutate(undefined)} loading={rollback.pending}>Roll back</Button>}>
      <ErrorNote error={promote.error ?? rollback.error} />
      {!data.models.length ? <Empty icon="cpu" title="No models registered">Models appear here after a training run completes.</Empty> : (
        <Table head={['Model', 'Kind', 'Data', 'Test top-1', 'Macro-F1', 'Status', '']}>
          {data.models.map((m) => (
            <tr key={m.model_id}>
              <td className="px-3 py-2 font-mono text-xs">{m.model_id} {m.synthetic && <Badge tone="warn">synthetic</Badge>}</td>
              <td className="px-3 py-2">{m.kind}</td>
              <td className="px-3 py-2 text-xs">{m.dataset_version}</td>
              <td className="px-3 py-2 tabular-nums">{fmt.pct(m.summary?.test_top1)}</td>
              <td className="px-3 py-2 tabular-nums">{fmt.pct(m.summary?.test_macro_f1)}</td>
              <td className="px-3 py-2"><StatusBadge status={m.status} /></td>
              <td className="px-3 py-2 text-right">{can(user, 'models:promote') && m.status !== 'production' && <Button size="sm" onClick={() => promote.mutate(m.model_id)}>Promote</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

function Experiments() {
  const { user } = useAuth();
  const list = useQuery<any[]>('/experiments', { poll: 5000 });
  const versions = useQuery<any[]>('/dataset/versions');
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<number | null>(null);
  const detail = useQuery<any>(sel ? `/experiments/${sel}` : null, { poll: 3000 });
  const [f, setF] = useState({ name: '', model_kind: 'lstm', dataset_version_id: '', hidden: '128', epochs: '60', seed: '13' });
  const create = useMutation(() => api('/experiments', { body: { name: f.name, model_kind: f.model_kind, dataset_version_id: f.dataset_version_id ? Number(f.dataset_version_id) : null, config: { hidden: Number(f.hidden), epochs: Number(f.epochs), seed: Number(f.seed) } } }), { invalidates: ['/experiments'], onSuccess: () => { toast('Experiment created'); setOpen(false); } });
  const run = useMutation((id: number) => api(`/experiments/${id}/run`, { method: 'POST' }), { invalidates: ['/experiments', '/models'] });
  return (
    <div className="space-y-4">
      <Card title="Experiments" action={can(user, 'experiments:write') && <Button variant="primary" icon="plus" onClick={() => setOpen(true)}>New experiment</Button>}>
        <ErrorNote error={run.error} />
        {!list.data?.length ? <Empty icon="flask" title="No experiments yet" /> : (
          <Table head={['#', 'Name', 'Model', 'Dataset', 'Status', 'Result', '']}>
            {list.data.map((e) => (
              <tr key={e.id}>
                <td className="px-3 py-2 text-ink-400">{e.id}</td>
                <td className="px-3 py-2"><button className="hover:text-nova-300" onClick={() => setSel(e.id)}>{e.name}</button></td>
                <td className="px-3 py-2">{e.model_kind}</td>
                <td className="px-3 py-2 text-xs">{e.dataset_version ?? <span className="text-amber-300">none</span>}</td>
                <td className="px-3 py-2"><StatusBadge status={e.status} /></td>
                <td className="max-w-xs truncate px-3 py-2 text-xs text-ink-400" title={e.error ?? e.model_id}>{e.model_id ?? e.error ?? ''}</td>
                <td className="px-3 py-2 text-right">{can(user, 'experiments:write') && !['queued', 'running'].includes(e.status) && <Button size="sm" icon="play" onClick={() => run.mutate(e.id)}>Run</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {detail.data && (
        <Card title={`Experiment #${detail.data.id} · ${detail.data.name}`} action={<Button size="sm" variant="ghost" icon="close" onClick={() => setSel(null)} aria-label="Close" />}>
          <div className="grid gap-4 md:grid-cols-2">
            <div><p className="label mb-1">Config</p><pre className="overflow-auto rounded-lg bg-ink-950 p-3 text-xs">{JSON.stringify(detail.data.config, null, 2)}</pre></div>
            <div><p className="label mb-1">Log</p><pre className="max-h-64 overflow-auto rounded-lg bg-ink-950 p-3 text-xs">{detail.data.log || detail.data.error || '(empty)'}</pre></div>
          </div>
        </Card>
      )}
      <Dialog open={open} onClose={() => setOpen(false)} title="New experiment"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button variant="primary" loading={create.pending} disabled={f.name.length < 3} onClick={() => create.mutate(undefined)}>Create</Button></>}>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2"><ErrorNote error={create.error} /></div>
          <Field label="Name">{(id) => <Input id={id} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />}</Field>
          <Field label="Model">{(id) => <Select id={id} value={f.model_kind} onChange={(e) => setF({ ...f, model_kind: e.target.value })}><option value="lstm">LSTM (baseline)</option><option value="gru">GRU</option><option value="pooled_logreg">Pooled logistic regression</option><option value="dtw_1nn">DTW 1-NN (reference)</option></Select>}</Field>
          <Field label="Dataset version" hint="Required to run. Versions contain only approved, consented data.">{(id) => <Select id={id} value={f.dataset_version_id} onChange={(e) => setF({ ...f, dataset_version_id: e.target.value })}><option value="">None yet</option>{versions.data?.map((v) => <option key={v.id} value={v.id}>{v.version} ({v.summary.recordings} rec.)</option>)}</Select>}</Field>
          <Field label="Hidden units">{(id) => <Input id={id} type="number" value={f.hidden} onChange={(e) => setF({ ...f, hidden: e.target.value })} />}</Field>
          <Field label="Max epochs">{(id) => <Input id={id} type="number" value={f.epochs} onChange={(e) => setF({ ...f, epochs: e.target.value })} />}</Field>
          <Field label="Seed">{(id) => <Input id={id} type="number" value={f.seed} onChange={(e) => setF({ ...f, seed: e.target.value })} />}</Field>
        </div>
      </Dialog>
    </div>
  );
}

function Contract() {
  const { data: m } = useQuery<ModelInfo>('/model/info');
  if (!m) return <Loading />;
  const c = m.feature_contract;
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title={c.name} subtitle={`${c.sequence_length} frames × ${c.feature_dim} features`} className="xl:col-span-2">
        <HBars label="Feature blocks" data={c.blocks.map((b) => ({ label: b.name.replaceAll('_', ' '), value: b.size }))} />
      </Card>
      <Card title="Definition">
        <dl className="space-y-3 text-sm">
          {[['Extractor', c.extractor], ['Normalisation', c.normalisation], ['Missing values', c.missing_values], ['Resampling', c.resampling], ['Non-manual features', c.non_manual_features]].map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd className="mt-0.5 text-ink-200">{v}</dd></div>)}
        </dl>
        <p className="muted mt-4 text-xs">The browser runs a TypeScript port of this contract that is tested for numerical parity with the Python training code.</p>
      </Card>
    </div>
  );
}

function NewSigners() {
  const { user } = useAuth();
  const versions = useQuery<any[]>('/dataset/versions');
  const runs = useQuery<any[]>('/evaluation/runs', { poll: 4000 });
  const model = useQuery<ModelInfo>('/model/info');
  const [vid, setVid] = useState('');
  const [open, setOpen] = useState<number | null>(null);
  const detail = useQuery<any>(open ? `/evaluation/runs/${open}` : null);
  const start = useMutation(() => api('/evaluation/runs', { body: { dataset_version_id: Number(vid), note: 'new-signer evaluation' } }),
    { invalidates: ['/evaluation/runs'], onSuccess: () => toast('Evaluation started') });
  return (
    <div className="space-y-4">
      <Notice title="Estimate accuracy on people the model has never seen">
        The INCLUDE results are not signer-independent. To measure generalisation, record consenting signers who are <b>not</b> in INCLUDE
        (Dataset Lab → Signers &amp; consent → Recording Studio), approve the clips through review, freeze them as a dataset version, then evaluate it here.
        Results are reported overall and per signer.
      </Notice>
      <Card title="Run an evaluation" subtitle={model.data?.available ? `Active model: ${model.data.model_id}` : 'No active model'}>
        {can(user, 'experiments:write') ? (
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Dataset version">{(id) => <Select id={id} value={vid} onChange={(e) => setVid(e.target.value)} className="w-72"><option value="">Choose…</option>{versions.data?.map((v) => <option key={v.id} value={v.id}>{v.version} · {v.summary.recordings} recordings · {v.summary.signers} signers</option>)}</Select>}</Field>
            <Button variant="primary" icon="play" disabled={!vid || !model.data?.available} loading={start.pending} onClick={() => start.mutate(undefined)}>Evaluate</Button>
          </div>
        ) : <p className="muted text-sm">Requires the researcher or admin role.</p>}
        {!versions.data?.length && <p className="muted mt-3 text-sm">No dataset versions yet: no new-signer recordings have been collected.</p>}
        <ErrorNote error={start.error} />
      </Card>
      <Card title="Evaluation runs">
        {!runs.data?.length ? <Empty icon="user" title="No new-signer evaluations yet">There are no results to show until recordings from new signers exist.</Empty> : (
          <Table head={['#', 'Model', 'Dataset', 'Status', 'Recordings', 'Signers', 'Top-1', 'Top-5', '']}>
            {runs.data.map((r) => (
              <tr key={r.id}>
                <td className="px-3 py-2 text-ink-400">{r.id}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.model_id}</td>
                <td className="px-3 py-2">{r.report.dataset_version}</td>
                <td className="px-3 py-2"><StatusBadge status={r.report.status === 'completed' ? 'succeeded' : r.report.status} /></td>
                <td className="px-3 py-2 tabular-nums">{r.report.overall?.n ?? '-'}</td>
                <td className="px-3 py-2 tabular-nums">{r.report.signers ?? '-'}</td>
                <td className="px-3 py-2 tabular-nums">{fmt.pct(r.report.overall?.top1)}</td>
                <td className="px-3 py-2 tabular-nums">{fmt.pct(r.report.overall?.top5)}</td>
                <td className="px-3 py-2 text-right"><Button size="sm" onClick={() => setOpen(r.id)}>Per signer</Button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {detail.data && (
        <Card title={`Run #${detail.data.id}: per signer`} action={<Button size="sm" variant="ghost" icon="close" aria-label="Close" onClick={() => setOpen(null)} />}>
          {detail.data.report.error ? <ErrorNote error={{ name: 'Error', status: 0, code: 'failed', message: detail.data.report.error } as any} /> : (
            <Table head={['Signer', 'Recordings', 'Top-1', 'Top-5', 'States']}>
              {Object.entries(detail.data.report.per_signer ?? {}).map(([sig, v]: [string, any]) => (
                <tr key={sig}><td className="px-3 py-2 font-mono text-xs">{sig}</td><td className="px-3 py-2">{v.n}</td><td className="px-3 py-2">{fmt.pct(v.top1)}</td><td className="px-3 py-2">{fmt.pct(v.top5)}</td><td className="px-3 py-2 text-xs text-ink-400">{Object.entries(v.states).map(([k, n]) => `${k} ${n}`).join(' · ')}</td></tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

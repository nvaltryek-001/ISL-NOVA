import { Segmented, HBars } from '../components/charts';
import { Icon, type IconName } from '../components/icons';
import { Card, ErrorNote, Loading, Meter, Notice, PageHeader, Stat, StatusBadge } from '../components/ui';
import { useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { useAuth } from '../lib/store';
import type { DatasetStats } from '../lib/types';

type Dash = {
  dataset: DatasetStats;
  model: { available: boolean; state: string; reason?: string; model_id?: string; synthetic?: boolean; n_classes?: number; metrics_summary?: Record<string, number> };
  experiments: Record<string, number>;
  me: null | { history: number; recognized: number; bookmarks: number; attempts: number; unread_notifications: number };
};

const READINESS_COLORS: Record<string, string> = {
  no_data: '#2c3657', collecting: '#22d3ee', insufficient_data: '#fbbf24', ready_for_review: '#a78bfa', approved_for_training: '#34d399', excluded: '#f43f5e',
};

export function DashboardPage() {
  const { user } = useAuth();
  const { data, error, loading, refetch } = useQuery<Dash>('/dashboard', { poll: 30000 });
  const { data: health } = useQuery<{ status: string; database: string; migrations: { applied: number; pending: string[] }; feature_contract: string }>('/health');
  const cats = useQuery<{ category: string; label: string; slots: number; verified: number }[]>('/signs/categories');

  return (
    <div className="space-y-6">
      <PageHeader kicker="ISL NOVA" title={user ? `Welcome, ${user.display_name}` : 'Indian Sign Language platform'}
        actions={<><Quick to="/live" icon="camera" label="Start recognition" primary /><Quick to="/signs" icon="book" label="Explore signs" /></>}>
        Every number here is read live from the database and model registry. Nothing is estimated or simulated.
      </PageHeader>

      <ErrorNote error={error} retry={refetch} />
      {loading && !data && <Loading rows={4} />}
      {data && (
        <>
          {!data.model.available && (
            <Notice tone="warn" title="No trained recognition model is active">
              Recognition will report <b>model unavailable</b> until a model trained on authentic, approved ISL recordings is promoted in the AI Laboratory.
              {data.model.reason && <span className="mt-1 block text-xs opacity-75">Server: {data.model.reason}</span>}
            </Notice>
          )}
          {data.model.synthetic && <Notice tone="warn" title="A synthetic smoke-test model is active">Its predictions are not Indian Sign Language and must not be reported.</Notice>}

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Class slots" value={data.dataset.class_slots} sub="active vocabulary IDs" icon="layers" tone="nova" />
            <Stat label="Verified signs" value={data.dataset.verified_classes} sub="by a qualified ISL reviewer" icon="check" tone="ok" />
            <Stat label="With recordings" value={data.dataset.classes_with_recordings} sub="classes with local media" icon="record" tone="signal" />
            <Stat label="Training-ready" value={data.dataset.classes_approved_for_training} sub={`≥${data.dataset.thresholds.min_approved_samples} samples, ≥${data.dataset.thresholds.min_signers} signers`} icon="rocket" tone="warn" />
            <Stat label="Approved samples" value={data.dataset.approved_samples} sub={`${data.dataset.recordings.total} recordings total`} icon="database" />
            <Stat label="Signers" value={data.dataset.signers} sub={`${data.dataset.active_consents} active consents`} icon="user" />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2" title="Dataset readiness" subtitle="Per-class data state across all 200 slots"
              action={<Link to="/dataset" className="text-sm text-nova-300 hover:underline">Open Dataset Lab</Link>}>
              <Segmented label="Readiness distribution" parts={Object.entries(data.dataset.readiness).map(([k, v]) => ({ label: k.replaceAll('_', ' '), value: v, color: READINESS_COLORS[k] }))} />
              <div className="mt-6 grid gap-4 md:grid-cols-3">
                <Meter label="Verified vocabulary" value={data.dataset.verified_classes} max={data.dataset.class_slots} tone="ok" />
                <Meter label="Classes with recordings" value={data.dataset.classes_with_recordings} max={data.dataset.class_slots} tone="signal" />
                <Meter label="Approved for training" value={data.dataset.classes_approved_for_training} max={data.dataset.class_slots} tone="warn" />
              </div>
              <p className="muted mt-5 text-xs">
                External reference: {data.dataset.external_source.name} lists {data.dataset.external_source.videos_listed.toLocaleString()} videos for these classes.
                They are <b className="text-ink-200">not downloaded</b> in this deployment.
              </p>
            </Card>

            <Card title="Recognition model" subtitle="Active model in the registry">
              {data.model.available ? (
                <dl className="space-y-3 text-sm">
                  <Row k="Model" v={<code className="text-xs">{data.model.model_id}</code>} />
                  <Row k="Classes" v={data.model.n_classes} />
                  <Row k="Test top-1" v={pct(data.model.metrics_summary?.test_top1)} />
                  <Row k="Test macro-F1" v={pct(data.model.metrics_summary?.test_macro_f1)} />
                </dl>
              ) : (
                <div className="space-y-3 text-sm">
                  <StatusBadge status="model_unavailable" />
                  <p className="text-ink-300">No model has been trained on authentic ISL data in this deployment, so no accuracy figures exist.</p>
                  <Link to="/ai" className="inline-flex items-center gap-1 text-nova-300 hover:underline">AI Laboratory <Icon name="chevron" size={14} /></Link>
                </div>
              )}
              <div className="mt-5 border-t border-ink-700 pt-4 text-xs">
                <p className="label mb-2">Experiments</p>
                <div className="flex flex-wrap gap-2">{Object.keys(data.experiments).length ? Object.entries(data.experiments).map(([k, v]) => <span key={k} className="inline-flex items-center gap-1"><StatusBadge status={k} />{v}</span>) : <span className="muted">None yet</span>}</div>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2" title="Vocabulary by category" subtitle="Slots / verified">
              {cats.data && <HBars label="Slots per category" data={cats.data.map((c) => ({ label: c.label, value: c.slots, secondary: c.verified }))} />}
            </Card>
            <div className="space-y-4">
              {data.me && (
                <Card title="Your activity">
                  <dl className="space-y-3 text-sm">
                    <Row k="Recognition history" v={data.me.history} />
                    <Row k="Recognised" v={data.me.recognized} />
                    <Row k="Bookmarks" v={data.me.bookmarks} />
                    <Row k="Practice attempts" v={data.me.attempts} />
                  </dl>
                </Card>
              )}
              <Card title="System health">
                {health ? (
                  <dl className="space-y-3 text-sm">
                    <Row k="API" v={<StatusBadge status={health.status === 'ok' ? 'succeeded' : 'blocked'} />} />
                    <Row k="Database" v={health.database} />
                    <Row k="Migrations" v={`${health.migrations.applied} applied${health.migrations.pending.length ? `, ${health.migrations.pending.length} pending` : ''}`} />
                    <Row k="Feature contract" v={<code className="text-xs">{health.feature_contract}</code>} />
                  </dl>
                ) : <Loading rows={2} />}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const pct = (v?: number) => (v === undefined || v === null ? '-' : `${(v * 100).toFixed(1)}%`);

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-ink-400">{k}</dt><dd className="text-right text-ink-100">{v}</dd></div>;
}

function Quick({ to, icon, label, primary }: { to: string; icon: IconName; label: string; primary?: boolean }) {
  return (
    <Link to={to} className={`inline-flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors ${primary ? 'bg-nova-500 text-white hover:bg-nova-400' : 'border border-ink-600 bg-ink-800 text-ink-100 hover:bg-ink-700'}`}>
      <Icon name={icon} size={16} />{label}
    </Link>
  );
}

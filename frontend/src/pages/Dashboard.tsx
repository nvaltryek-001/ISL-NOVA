import { HBars } from '../components/charts';
import { HandArt } from '../components/HandArt';
import { Icon, type IconName } from '../components/icons';
import { Badge, Card, CountUp, ErrorNote, Loading, Notice, StatusBadge } from '../components/ui';
import { useT } from '../i18n';
import { useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { can, useAuth } from '../lib/store';
import type { DatasetStats } from '../lib/types';

type Dash = {
  dataset: DatasetStats;
  model: { available: boolean; state: string; reason?: string; model_id?: string; synthetic?: boolean; n_classes?: number; metrics_summary?: Record<string, number> };
  experiments: Record<string, number>;
  me: null | { history: number; recognized: number; bookmarks: number; attempts: number; unread_notifications: number };
};

const ACTIONS: { to: string; icon: IconName; title: string; text: string; tint: string }[] = [
  { to: '/live', icon: 'camera', title: 'Live Recognition', text: 'Sign in front of your camera and see the meaning instantly.', tint: 'from-violet-500/15 to-fuchsia-500/5 text-violet-600 dark:text-violet-300' },
  { to: '/conversation', icon: 'chat', title: 'Conversation', text: 'Sign several words in a row and build a sentence.', tint: 'from-cyan-500/15 to-sky-500/5 text-cyan-700 dark:text-cyan-300' },
  { to: '/practice', icon: 'hand', title: 'Practice Coach', text: 'Copy a reference sign and get tips on shape and movement.', tint: 'from-emerald-500/15 to-teal-500/5 text-emerald-700 dark:text-emerald-300' },
  { to: '/text-to-sign', icon: 'type', title: 'Text to Sign', text: 'Type in English, हिन्दी or ಕನ್ನಡ and watch the signs.', tint: 'from-amber-500/15 to-orange-500/5 text-amber-700 dark:text-amber-300' },
  { to: '/signs', icon: 'book', title: 'Sign Explorer', text: 'Browse all 200 signs with meanings in three languages.', tint: 'from-indigo-500/15 to-blue-500/5 text-indigo-600 dark:text-indigo-300' },
  { to: '/academy', icon: 'cap', title: 'Learning Academy', text: 'Lessons, quizzes, streaks and badges.', tint: 'from-rose-500/15 to-pink-500/5 text-rose-600 dark:text-rose-300' },
];

export function DashboardPage() {
  const { user } = useAuth();
  const t = useT();
  const { data, error, loading, refetch } = useQuery<Dash>('/dashboard', { poll: 30000 });
  const staff = can(user, 'dataset:review') || can(user, 'admin:users');
  const { data: health } = useQuery<{ status: string; database: string; migrations: { applied: number; pending: string[] }; feature_contract: string }>(staff ? '/health' : null);
  const cats = useQuery<{ category: string; label: string; slots: number; verified: number }[]>('/signs/categories');
  const m = data?.model;
  const top1 = m?.available && !m.synthetic ? m.metrics_summary?.test_top1 : undefined;
  const top5 = m?.available && !m.synthetic ? m.metrics_summary?.test_top5 : undefined;

  return (
    <div className="space-y-8">
      <section className="hero-band">
        <span className="orb -right-10 -top-16 size-64 bg-violet-400/40" aria-hidden />
        <span className="orb -bottom-24 left-1/3 size-72 bg-cyan-300/30 [animation-delay:-6s]" aria-hidden />
        <div className="relative grid items-center gap-6 md:grid-cols-[1.35fr_1fr]">
          <div className="stagger">
            <p className="label text-nova-300">{t('Indian Sign Language, made accessible')}</p>
            <h1 className="mt-2 text-3xl font-semibold leading-tight text-fg md:text-[40px]">
              {user ? `${t('Welcome')}, ${user.display_name}` : <>{t('Beyond gestures.')} <span className="text-gradient">{t('Towards understanding.')}</span></>}
            </h1>
            <p className="mt-3 max-w-xl text-[15px] text-ink-300">
              {t('Recognise, learn and practise Indian Sign Language in English, हिन्दी and ಕನ್ನಡ. Your camera video stays on your device.')}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Quick to="/live" icon="camera" label={t('Start recognition')} primary />
              <Quick to="/signs" icon="book" label={t('Explore signs')} />
            </div>
          </div>
          <HandArt className="mx-auto hidden w-full max-w-[340px] md:block" />
        </div>
      </section>

      <ErrorNote error={error} retry={refetch} />
      {loading && !data && <Loading rows={4} />}
      {data && (
        <>
          {!m?.available && (
            <Notice tone="warn" title="No trained recognition model is active">
              {t('Recognition starts working as soon as an administrator activates a model in the AI Laboratory.')}
            </Notice>
          )}
          {m?.synthetic && <Notice tone="warn" title="A synthetic smoke-test model is active">{t('Its predictions are not Indian Sign Language.')}</Notice>}

          <div className="stagger grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Highlight icon="layers" label={t('Signs in the vocabulary')} value={<CountUp value={data.dataset.class_slots} />} />
            <Highlight icon="globe" label={t('Languages')} value={<CountUp value={3} />} sub="English · हिन्दी · ಕನ್ನಡ" />
            {top1 !== undefined
              ? <Highlight icon="sparkle" label={t('Test accuracy (top-1)')} value={<CountUp value={top1 * 100} decimals={1} suffix="%" />}
                sub={top5 !== undefined ? `${t('Top-5')}: ${(top5 * 100).toFixed(1)}%` : undefined} />
              : <Highlight icon="sparkle" label={t('Recognition model')} value={m?.available ? t('Active') : t('Off')} />}
            <Highlight icon="hand" label={user ? t('Your recognitions') : t('Categories')}
              value={<CountUp value={user && data.me ? data.me.history : (cats.data?.length ?? 0)} />}
              sub={user && data.me ? `${data.me.attempts} ${t('practice attempts')}` : undefined} />
          </div>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-fg">{t('What would you like to do?')}</h2>
            <div className="stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {ACTIONS.map((a) => (
                <Link key={a.to} to={a.to} className="card lift group flex items-start gap-4 p-5">
                  <span className={`tile-icon grid size-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br ${a.tint}`}><Icon name={a.icon} size={22} /></span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-1 font-medium text-fg">{t(a.title)}<Icon name="chevron" size={14} className="text-ink-500 transition-transform group-hover:translate-x-1" /></span>
                    <span className="muted mt-1 block text-sm">{t(a.text)}</span>
                  </span>
                </Link>
              ))}
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2" title="Vocabulary by category" subtitle={t('Signs in each topic')}>
              {cats.data && <HBars label="Signs per category" data={cats.data.map((c) => ({ label: c.label, value: c.slots }))} />}
            </Card>
            <div className="space-y-4">
              <Card title="Recognition model">
                {m?.available ? (
                  <dl className="space-y-3 text-sm">
                    <Row k={t('Status')} v={<Badge tone="ok"><span className="live-dot size-1.5 rounded-full bg-current" />{t('Active')}</Badge>} />
                    <Row k={t('Signs')} v={m.n_classes} />
                    <Row k={t('Test top-1')} v={pct(m.metrics_summary?.test_top1)} />
                    <Row k={t('Test macro-F1')} v={pct(m.metrics_summary?.test_macro_f1)} />
                  </dl>
                ) : <p className="muted text-sm">{t('No model is active.')}</p>}
                <Link to="/ai" className="mt-4 inline-flex items-center gap-1 text-sm text-nova-300 hover:underline">{t('AI Laboratory')} <Icon name="chevron" size={14} /></Link>
              </Card>
              {data.me && (
                <Card title="Your activity">
                  <dl className="space-y-3 text-sm">
                    <Row k={t('Recognition history')} v={data.me.history} />
                    <Row k={t('Recognised')} v={data.me.recognized} />
                    <Row k={t('Bookmarks')} v={data.me.bookmarks} />
                    <Row k={t('Practice attempts')} v={data.me.attempts} />
                  </dl>
                </Card>
              )}
            </div>
          </div>

          {staff && (
            <section>
              <h2 className="mb-3 text-lg font-semibold text-fg">{t('Workspace')}</h2>
              <div className="grid gap-4 xl:grid-cols-3">
                <Card className="xl:col-span-2" title="Dataset" action={<Link to="/dataset" className="text-sm text-nova-300 hover:underline">{t('Open Dataset Lab')}</Link>}>
                  <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                    <Mini k={t('Class slots')} v={data.dataset.class_slots} />
                    <Mini k={t('Verified signs')} v={data.dataset.verified_classes} />
                    <Mini k={t('Approved samples')} v={data.dataset.approved_samples} />
                    <Mini k={t('Signers')} v={data.dataset.signers} />
                  </dl>
                </Card>
                <Card title="System health">
                  {health ? (
                    <dl className="space-y-3 text-sm">
                      <Row k="API" v={<StatusBadge status={health.status === 'ok' ? 'succeeded' : 'blocked'} />} />
                      <Row k={t('Database')} v={health.database} />
                      <Row k={t('Migrations')} v={health.migrations.applied} />
                    </dl>
                  ) : <Loading rows={2} />}
                </Card>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

const pct = (v?: number) => (v === undefined || v === null ? '-' : `${(v * 100).toFixed(1)}%`);

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-ink-400">{k}</dt><dd className="text-right text-ink-100">{v}</dd></div>;
}

function Mini({ k, v }: { k: string; v: number }) {
  return <div><dt className="label">{k}</dt><dd className="mt-1 font-display text-2xl font-semibold tabular-nums text-fg"><CountUp value={v} /></dd></div>;
}

function Highlight({ icon, label, value, sub }: { icon: IconName; label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="card lift relative overflow-hidden p-5">
      <span className="absolute -right-6 -top-6 size-24 rounded-full bg-nova-500/10" aria-hidden />
      <Icon name={icon} className="relative text-nova-400" />
      <p className="relative mt-3 font-display text-3xl font-semibold tabular-nums text-fg">{value}</p>
      <p className="relative mt-1 text-sm text-ink-300">{label}</p>
      {sub && <p className="relative mt-0.5 text-xs text-ink-500">{sub}</p>}
    </div>
  );
}

function Quick({ to, icon, label, primary }: { to: string; icon: IconName; label: string; primary?: boolean }) {
  return (
    <Link to={to} className={`inline-flex h-11 items-center gap-2 rounded-xl px-5 text-sm font-medium transition-all hover:-translate-y-0.5 active:translate-y-0 ${primary ? 'bg-gradient-to-r from-nova-500 to-indigo-glow text-white shadow-[0_10px_24px_-10px_rgba(124,58,237,.7)] hover:shadow-[0_14px_30px_-10px_rgba(124,58,237,.8)]' : 'border border-ink-600 bg-ink-850 text-ink-100 shadow-sm hover:bg-ink-800'}`}>
      <Icon name={icon} size={16} />{label}
    </Link>
  );
}

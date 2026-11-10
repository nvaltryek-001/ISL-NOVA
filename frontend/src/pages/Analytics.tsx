import { useState } from 'react';
import { LineChart } from '../components/charts';
import { Card, Empty, ErrorNote, Loading, PageHeader, Select, Table } from '../components/ui';
import { useT } from '../i18n';
import { useQuery } from '../lib/query';
import { Link } from '../lib/router';

type SignRow = { sign_id: string; name: string; attempts: number; accuracy: number };
type Overview = {
  days: string[];
  series: { learning_attempts: number[]; saved_recognitions: number[]; active_users: number[]; new_users: number[] };
  totals: { learning_attempts: number; saved_recognitions: number; active_users: number; new_users: number; attempt_accuracy: number | null };
  modes: Record<string, number>; recognition_states: Record<string, number>;
  most_practised: SignRow[]; hardest: SignRow[];
  corrections: { model_said: string; user_corrected_to: string; count: number }[]; note: string;
};

export function AnalyticsPage() {
  const t = useT();
  const [days, setDays] = useState('30');
  const { data, error } = useQuery<Overview>(`/analytics/overview?days=${days}`);
  const pct = (x: number | null) => (x === null ? '–' : `${Math.round(x * 100)}%`);
  const yMax = (v: number[]) => Math.max(4, ...v);
  return (
    <>
      <PageHeader title="Analytics"
        actions={<Select aria-label="Time window" value={days} onChange={(e) => setDays(e.target.value)}>
          {['7', '30', '90', '365'].map((d) => <option key={d} value={d}>{d} {t('days')}</option>)}</Select>}>
        {t('Aggregate usage and learning statistics from real activity. No individual data.')}
      </PageHeader>
      <ErrorNote error={error} />
      {!data ? !error && <Loading /> : (
        <div className="grid gap-4 xl:grid-cols-3">
          <div className="grid grid-cols-2 gap-3 xl:col-span-3 md:grid-cols-5">
            {([['Active users', data.totals.active_users], ['New users', data.totals.new_users], ['Learning attempts', data.totals.learning_attempts],
              ['Attempt accuracy', pct(data.totals.attempt_accuracy)], ['Saved recognitions', data.totals.saved_recognitions]] as const).map(([k, v]) => (
              <div key={k} className="card p-4"><p className="label">{t(k)}</p><p className="mt-1 font-display text-2xl font-semibold text-fg">{v}</p></div>
            ))}
          </div>
          <Card className="xl:col-span-2" title="Activity per day" subtitle={`${data.days[0]} – ${data.days.at(-1)}`}>
            <LineChart label={t('Activity per day')} yMax={yMax([...data.series.learning_attempts, ...data.series.saved_recognitions])}
              series={[{ name: t('Learning attempts'), values: data.series.learning_attempts }, { name: t('Saved recognitions'), values: data.series.saved_recognitions }]} />
            <div className="mt-4"><LineChart label={t('Active users')} height={120} yMax={yMax(data.series.active_users)}
              series={[{ name: t('Active users'), values: data.series.active_users }, { name: t('New users'), values: data.series.new_users }]} /></div>
          </Card>
          <Card title="Modes and recognition states">
            <dl className="space-y-2 text-sm">
              {Object.entries(data.modes).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-ink-400">{k}</dt><dd>{v}</dd></div>)}
              {Object.entries(data.recognition_states).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-ink-400">{k}</dt><dd>{v}</dd></div>)}
            </dl>
            {!Object.keys(data.modes).length && !Object.keys(data.recognition_states).length && <p className="muted text-sm">{t('No activity in this window.')}</p>}
          </Card>
          <SignTable title="Most practised signs" rows={data.most_practised} />
          <SignTable title="Hardest signs" subtitle="Lowest accuracy, at least 5 attempts" rows={data.hardest} />
          <Card title="Most common corrections" subtitle="Saved results that users corrected">
            {!data.corrections.length ? <p className="muted text-sm">{t('No corrections yet.')}</p> : (
              <ul className="space-y-2 text-sm">{data.corrections.map((c, i) => (
                <li key={i} className="flex justify-between gap-2"><span>{c.model_said} → <span className="text-fg">{c.user_corrected_to}</span></span><span className="text-ink-400">{c.count}</span></li>))}
              </ul>
            )}
          </Card>
          <p className="muted text-xs xl:col-span-3">{data.note}</p>
        </div>
      )}
    </>
  );
}

function SignTable({ title, subtitle, rows }: { title: string; subtitle?: string; rows: SignRow[] }) {
  return (
    <Card title={title} subtitle={subtitle}>
      {!rows.length ? <Empty icon="book" title="No data yet" /> : (
        <Table head={['Sign', 'Attempts', 'Accuracy']}>
          {rows.map((r) => (
            <tr key={r.sign_id}><td className="px-3 py-2"><Link to={`/signs/${r.sign_id}`} className="hover:text-nova-300">{r.name}</Link></td>
              <td className="px-3 py-2">{r.attempts}</td><td className="px-3 py-2">{Math.round(r.accuracy * 100)}%</td></tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

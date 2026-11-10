import { useState } from 'react';
import { Icon } from '../components/icons';
import { Badge, Button, Card, Empty, ErrorNote, Loading, Meter, Notice, PageHeader, StatusBadge, Tabs } from '../components/ui';
import { useT } from '../i18n';
import { api } from '../lib/api';
import { useQuery } from '../lib/query';
import { Link } from '../lib/router';
import { toast, useAuth } from '../lib/store';

type Lessons = { verified_signs: number; include_unverified: boolean; lessons: { category: string; label: string; signs: { sign_id: string; canonical_sign_name: string; verification_status: string; attempts: number; correct: number }[] }[] };
type Quiz = { available: boolean; reason?: string; questions: { sign_id: string; prompt: string; reference?: { source_name: string; source_url: string } | null; options: { sign_id: string; text: string }[] }[] };
type Progress = { signs_practised: number; attempts: number; correct: number; accuracy: number | null; difficult: { sign_id: string; canonical_sign_name: string; attempts: number; correct: number }[] };

export function AcademyPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<'lessons' | 'quiz' | 'progress'>('lessons');
  const [preview, setPreview] = useState(false);
  const lessons = useQuery<Lessons>(`/learning/lessons?include_unverified=${preview}`);
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Learning Academy" title="Learning Academy"
        actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'lessons', label: 'Lessons' }, { id: 'quiz', label: 'Quiz' }, { id: 'progress', label: 'My progress' }]} />}>
        Lessons and quizzes use only reviewer-verified signs and meanings. The Academy records your answers but does not score your signing; that would need validated assessment.
      </PageHeader>
      {tab === 'lessons' && (
        <>
          {lessons.data && lessons.data.verified_signs === 0 && !preview && (
            <Card><Empty icon="cap" title="No verified lessons yet" action={<Button onClick={() => setPreview(true)}>Preview unverified vocabulary</Button>}>
              Lessons open as qualified ISL reviewers verify signs. You can preview the unverified vocabulary, clearly labelled.
            </Empty></Card>
          )}
          {preview && <Notice tone="warn" title="Previewing unverified vocabulary">These entries are not confirmed by an ISL reviewer. Use the reference source to see the sign. <button className="underline" onClick={() => setPreview(false)}>Hide unverified</button></Notice>}
          <ErrorNote error={lessons.error} />
          {lessons.loading && !lessons.data && <Loading rows={4} />}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {lessons.data?.lessons.map((l, i) => {
              const practised = l.signs.filter((s) => s.attempts > 0).length;
              return (
                <Card key={l.category} title={<span className="flex items-center gap-2"><span className="grid size-7 place-items-center rounded-lg bg-nova-500/15 text-xs text-nova-300">{i + 1}</span>{l.label}</span>}>
                  <Meter label="Practised" value={practised} max={l.signs.length} tone="signal" />
                  <ul className="mt-4 flex flex-wrap gap-1.5">
                    {l.signs.map((s) => (
                      <li key={s.sign_id}><Link to={`/signs/${s.sign_id}`} className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs hover:text-fg ${s.verification_status === 'verified' ? 'border-emerald-500/40 text-emerald-200' : 'border-ink-600 text-ink-300'}`}>
                        {s.canonical_sign_name}{s.attempts > 0 && <span className="text-ink-500">{s.correct}/{s.attempts}</span>}
                      </Link></li>
                    ))}
                  </ul>
                </Card>
              );
            })}
          </div>
        </>
      )}
      {tab === 'quiz' && <QuizView signedIn={!!user} />}
      {tab === 'progress' && (user ? <ProgressView /> : <Card><Empty icon="user" title="Sign in to track progress" /></Card>)}
    </div>
  );
}

function QuizView({ signedIn }: { signedIn: boolean }) {
  const quiz = useQuery<Quiz>('/learning/quiz?n=5', { staleMs: 0 });
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  if (quiz.loading && !quiz.data) return <Loading />;
  if (!quiz.data?.available) return <Card><Empty icon="cap" title="Quiz not available yet">{quiz.data?.reason}</Empty></Card>;
  const qs = quiz.data.questions;
  if (i >= qs.length) return (
    <Card className="text-center"><p className="font-display text-4xl font-semibold text-fg">{score} / {qs.length}</p><p className="muted mt-2">Answers recorded{signedIn ? ' to your progress' : ''}.</p>
      <Button className="mt-5" variant="primary" onClick={() => { setI(0); setScore(0); setPicked(null); quiz.refetch(); }}>New quiz</Button></Card>
  );
  const q = qs[i];
  const answer = async (o: string) => {
    if (picked) return;
    setPicked(o);
    const ok = o === q.sign_id;
    if (ok) setScore(score + 1);
    if (signedIn) await api('/learning/attempts', { body: { sign_id: q.sign_id, mode: 'quiz', correct: ok, answer: o } }).catch((e) => toast(e.message, 'error'));
  };
  return (
    <Card title={`Question ${i + 1} of ${qs.length}`} action={<Badge tone="nova">Score {score}</Badge>}>
      <p className="text-lg text-fg">{q.prompt}</p>
      {q.reference && <a className="mt-1 inline-block text-sm text-nova-300 hover:underline" href={q.reference.source_url} target="_blank" rel="noreferrer noopener">View reference ({q.reference.source_name})</a>}
      <div className="mt-5 grid gap-2 md:grid-cols-2">
        {q.options.map((o) => {
          const state = !picked ? '' : o.sign_id === q.sign_id ? 'border-emerald-500 bg-emerald-500/10' : o.sign_id === picked ? 'border-rose-500 bg-rose-500/10' : 'opacity-60';
          return <button key={o.sign_id} disabled={!!picked} onClick={() => answer(o.sign_id)} className={`rounded-xl border border-ink-600 px-4 py-3 text-left transition-colors hover:border-nova-400 ${state}`}>{o.text}</button>;
        })}
      </div>
      {picked && <div className="mt-4 flex justify-end"><Button variant="primary" onClick={() => { setI(i + 1); setPicked(null); }}>Next</Button></div>}
    </Card>
  );
}

type Review = { due: { sign_id: string; canonical_sign_name: string; review_box: number; attempts: number; correct: number }[]; due_count: number; upcoming: number };

function ReviewCard() {
  const t = useT();
  const { data } = useQuery<Review>('/learning/review');
  if (!data) return null;
  return (
    <Card title="Due for review today" subtitle="Spaced repetition: correct answers come back after 1, 2, 4, 8 and 16 days; mistakes come back today">
      {!data.due.length ? <p className="muted text-sm">{data.upcoming ? t('Nothing due now. Signs you practised come back on their review day.') : t('Practise a few signs to start your review schedule.')}</p> : (
        <ul className="space-y-2 text-sm">{data.due.slice(0, 12).map((d) => (
          <li key={d.sign_id} className="flex items-center justify-between gap-2">
            <Link to={`/signs/${d.sign_id}`} className="hover:text-nova-300">{d.canonical_sign_name}</Link>
            <span className="flex items-center gap-2 text-xs text-ink-400">{d.correct}/{d.attempts}
              <Link to={`/practice?sign=${d.sign_id}`} className="rounded border border-ink-600 px-2 py-0.5 text-ink-200 hover:border-nova-400">{t('Practise')}</Link></span>
          </li>))}
        </ul>
      )}
      <p className="muted mt-3 text-xs">{data.due_count} {t('due')} · {data.upcoming} {t('scheduled later')}</p>
    </Card>
  );
}

type Achievements = {
  today: number; daily_goal: number;
  attempts: number; correct: number; signs_practised: number; current_streak: number; best_streak: number;
  points: number; this_week: number; weekly_goal: number; badges: { id: string; title: string; description: string; earned: boolean }[];
};

function AchievementsCard() {
  const t = useT();
  const { data } = useQuery<Achievements>('/learning/achievements');
  if (!data) return null;
  const pct = Math.min(100, Math.round((data.this_week / data.weekly_goal) * 100));
  return (
    <Card className="md:col-span-3" title="Streaks and badges" subtitle="Earned from your own quiz and Practice Coach attempts">
      <div className="grid gap-4 sm:grid-cols-4">
        <div><p className="label">{t('Current streak')}</p><p className="font-display text-2xl font-semibold text-fg">{data.current_streak} <span className="text-sm font-normal text-ink-400">{t('days')}</span></p></div>
        <div><p className="label">{t('Best streak')}</p><p className="font-display text-2xl font-semibold text-fg">{data.best_streak} <span className="text-sm font-normal text-ink-400">{t('days')}</span></p></div>
        <div><p className="label">{t('Today')}</p><p className="font-display text-2xl font-semibold text-fg">{data.today} <span className="text-sm font-normal text-ink-400">/ {data.daily_goal}</span></p>
          <p className="text-xs text-ink-400">{data.today >= data.daily_goal ? t('Daily goal reached') : t('Daily goal')} · {data.points} {t('points')}</p></div>
        <div>
          <p className="label">{t('This week')}</p>
          <p className="text-sm text-ink-300">{data.this_week} / {data.weekly_goal} {t('attempts')}</p>
          <div className="mt-1 h-2 rounded-full bg-ink-700" role="progressbar" aria-label={t('Weekly goal')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
            <div className="h-2 rounded-full bg-nova-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {data.badges.map((b) => (
          <li key={b.id} className={`rounded-lg border p-3 text-sm ${b.earned ? 'border-nova-500/50' : 'border-ink-700 opacity-70'}`}>
            <p className="flex items-center gap-2 font-medium text-fg"><Icon name={b.earned ? 'check' : 'sparkle'} />{t(b.title)}</p>
            <p className="mt-1 text-xs text-ink-400">{t(b.description)}</p>
            <p className="sr-only">{b.earned ? t('Earned') : t('Not earned yet')}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ProgressView() {
  const { data } = useQuery<Progress>('/learning/progress');
  if (!data) return <Loading />;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <AchievementsCard />
      <ReviewCard />
      <Card title="Summary">
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between"><dt className="text-ink-400">Signs practised</dt><dd>{data.signs_practised}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-400">Attempts</dt><dd>{data.attempts}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-400">Correct answers</dt><dd>{data.correct}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-400">Quiz accuracy</dt><dd>{data.accuracy === null ? '-' : `${Math.round(data.accuracy * 100)}%`}</dd></div>
        </dl>
      </Card>
      <Card className="md:col-span-2" title="Review these signs" subtitle="Below 60% correct after two or more attempts">
        {!data.difficult.length ? <p className="muted text-sm">Nothing to review yet.</p> : (
          <ul className="space-y-2">{data.difficult.map((d) => <li key={d.sign_id} className="flex justify-between text-sm"><Link to={`/signs/${d.sign_id}`} className="hover:text-nova-300">{d.canonical_sign_name}</Link><span className="flex items-center gap-2"><StatusBadge status="needs_changes" />{d.correct}/{d.attempts}</span></li>)}</ul>
        )}
      </Card>
    </div>
  );
}

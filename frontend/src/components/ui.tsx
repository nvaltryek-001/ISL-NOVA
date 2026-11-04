// ISL NOVA design system primitives.
import clsx from 'clsx';
import {
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes, useEffect, useId, useRef,
} from 'react';
import type { ApiError } from '../lib/api';
import { toasts, useStore } from '../lib/store';
import { Icon, type IconName } from './icons';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'signal';
const V: Record<Variant, string> = {
  primary: 'bg-nova-500 text-white hover:bg-nova-600 shadow-[0_8px_24px_-12px_color-mix(in_oklab,var(--color-nova-500)_80%,transparent)]',
  secondary: 'bg-ink-850 text-ink-100 border border-ink-600 shadow-sm hover:border-ink-500 hover:bg-ink-800',
  ghost: 'text-ink-300 hover:bg-ink-800 hover:text-fg',
  danger: 'bg-rose-600 text-white hover:bg-rose-700',
  signal: 'bg-signal text-on-accent hover:brightness-110',
};

export function Button({ variant = 'secondary', size = 'md', icon, loading, children, className, ...rest }:
  { variant?: Variant; size?: 'sm' | 'md' | 'lg'; icon?: IconName; loading?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={clsx('inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all active:scale-[.98] disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' ? 'h-8 px-3 text-xs' : size === 'lg' ? 'h-14 px-6 text-lg' : 'h-10 px-4 text-sm', V[variant], className)}
      disabled={loading || rest.disabled} aria-busy={loading || undefined} {...rest}
    >
      {loading ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden /> : icon && <Icon name={icon} size={size === 'lg' ? 22 : 16} />}
      {children}
    </button>
  );
}

export function Card({ children, className, title, action, subtitle }: { children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <section className={clsx('card rise p-5', className)}>
      {(title || action) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold text-fg">{title}</h2>}
            {subtitle && <p className="muted mt-0.5 text-sm">{subtitle}</p>}
          </div>
          {action && <div className="min-w-0 max-w-full">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES = {
  neutral: 'bg-ink-700/60 text-ink-200 ring-ink-600',
  nova: 'bg-nova-500/15 text-nova-300 ring-nova-500/30',
  signal: 'bg-cyan-400/10 text-cyan-300 ring-cyan-400/30',
  ok: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
  warn: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
  bad: 'bg-rose-500/10 text-rose-300 ring-rose-500/30',
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = 'neutral', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={clsx('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset', TONES[tone], className)}>{children}</span>;
}

const STATUS: Record<string, [Tone, string]> = {
  proposed: ['neutral', 'Proposed'], reference_found: ['signal', 'Reference found'], review_pending: ['warn', 'Review pending'],
  verified: ['ok', 'Verified'], rejected: ['bad', 'Rejected'],
  no_data: ['neutral', 'No data'], collecting: ['signal', 'Collecting'], insufficient_data: ['warn', 'Insufficient data'],
  ready_for_review: ['nova', 'Ready for review'], approved_for_training: ['ok', 'Approved for training'], excluded: ['bad', 'Excluded'],
  pending_review: ['warn', 'Pending review'], approved: ['ok', 'Approved'], deleted: ['neutral', 'Deleted'],
  recognized: ['ok', 'Recognized'], uncertain: ['warn', 'Uncertain'], unknown: ['bad', 'Unknown sign'],
  insufficient_input: ['neutral', 'Insufficient input'], model_unavailable: ['bad', 'Model unavailable'], camera_unavailable: ['bad', 'Camera unavailable'],
  created: ['neutral', 'Created'], queued: ['signal', 'Queued'], running: ['nova', 'Running'], succeeded: ['ok', 'Succeeded'],
  failed: ['bad', 'Failed'], blocked: ['warn', 'Blocked'], candidate: ['neutral', 'Candidate'], production: ['ok', 'Production'], archived: ['neutral', 'Archived'],
  pending: ['neutral', 'Pending'], draft: ['warn', 'Draft'], source_gloss: ['signal', 'Source gloss'], open: ['warn', 'Open'], resolved: ['ok', 'Resolved'], dismissed: ['neutral', 'Dismissed'],
  needs_changes: ['warn', 'Needs changes'], completed: ['ok', 'Completed'], processing: ['nova', 'Processing'], extractor_unavailable: ['warn', 'Extractor unavailable'], expired: ['neutral', 'Expired'],
};

export function StatusBadge({ status }: { status: string }) {
  const [tone, label] = STATUS[status] ?? ['neutral', status];
  return <Badge tone={tone}><span className="size-1.5 rounded-full bg-current opacity-80" aria-hidden />{label}</Badge>;
}

export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink-200">{label}</label>
      {children(id)}
      {hint && !error && <p className="muted text-xs">{hint}</p>}
      {error && <p className="text-xs text-rose-300" role="alert">{error}</p>}
    </div>
  );
}

export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={clsx('field', p.className)} />;
export const Textarea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea rows={3} {...p} className={clsx('field', p.className)} />;
export const Select = ({ children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={clsx('field pr-8', p.className)}>{children}</select>;

export function Dialog({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const hid = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} onClose={onClose} onCancel={onClose} aria-labelledby={hid}
      className={clsx('m-auto w-[calc(100%-2rem)] rounded-2xl border border-ink-600 bg-ink-850 p-0 text-ink-100 shadow-[var(--shadow-pop)] backdrop:bg-ink-950/70 backdrop:backdrop-blur-sm', wide ? 'max-w-3xl' : 'max-w-lg')}>
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <header className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
            <h2 id={hid} className="text-base font-semibold">{title}</h2>
            <button className="rounded-md p-1 text-ink-400 hover:bg-ink-700 hover:text-fg" onClick={onClose} aria-label="Close dialog"><Icon name="close" /></button>
          </header>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-ink-700 px-5 py-3">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}

export function Table({ head, children, empty, className }: { head: ReactNode[]; children: ReactNode; empty?: ReactNode; className?: string }) {
  return (
    <div className={clsx('overflow-x-auto rounded-xl border border-ink-700', className)}>
      <table className="w-full text-left text-sm">
        <thead className="bg-ink-800/70 text-xs uppercase tracking-wider text-ink-400">
          <tr>{head.map((h, i) => <th key={i} scope="col" className="whitespace-nowrap px-3 py-2.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-ink-700/70">{children}</tbody>
      </table>
      {empty}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="flex max-w-full gap-1 overflow-x-auto rounded-xl border border-ink-700 bg-ink-850 p-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx('whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors', value === t.id ? 'bg-ink-700 text-fg' : 'text-ink-400 hover:text-ink-100')}>
          {t.label}{t.count !== undefined && <span className="ml-1.5 text-xs text-ink-400">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Empty({ icon = 'info', title, children, action }: { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="grid size-11 place-items-center rounded-xl bg-ink-800 text-ink-400 ring-1 ring-ink-700"><Icon name={icon} size={20} /></div>
      <p className="font-medium text-ink-100">{title}</p>
      {children && <div className="muted max-w-md text-sm">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error, retry }: { error?: ApiError | null; retry?: () => void }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm">
      <Icon name="alert" className="mt-0.5 shrink-0 text-rose-300" />
      <div className="flex-1">
        <p className="font-medium text-rose-200">{error.code === 'offline' ? 'You appear to be offline' : 'Something went wrong'}</p>
        <p className="mt-0.5 text-rose-200/80">{error.message}</p>
      </div>
      {retry && <Button size="sm" onClick={retry} icon="refresh">Retry</Button>}
    </div>
  );
}

export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warn' | 'ok'; title: string; children?: ReactNode }) {
  const c = tone === 'warn' ? 'border-amber-500/30 bg-amber-500/5 text-amber-200' : tone === 'ok' ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200' : 'border-cyan-400/25 bg-cyan-400/5 text-cyan-100';
  return (
    <div className={clsx('flex gap-3 rounded-xl border p-4 text-sm', c)} role="note">
      <Icon name={tone === 'warn' ? 'alert' : tone === 'ok' ? 'check' : 'info'} className="mt-0.5 shrink-0" />
      <div><p className="font-medium">{title}</p>{children && <div className="mt-1 opacity-85">{children}</div>}</div>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton rounded-lg', className)} aria-hidden />;
}

export function Loading({ rows = 3 }: { rows?: number }) {
  return <div className="space-y-2" role="status" aria-label="Loading">{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>;
}

export function Stat({ label, value, sub, tone = 'neutral', icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'neutral' | 'nova' | 'signal' | 'ok' | 'warn'; icon?: IconName }) {
  const accent = { neutral: 'text-ink-300', nova: 'text-nova-300', signal: 'text-cyan-300', ok: 'text-emerald-300', warn: 'text-amber-300' }[tone];
  return (
    <div className="card rise flex min-w-0 flex-col gap-1 p-4">
      <div className="flex items-start justify-between gap-2"><span className="label min-w-0 hyphens-auto [overflow-wrap:anywhere]">{label}</span>{icon && <Icon name={icon} className={`${accent} shrink-0`} />}</div>
      <span className="font-display text-3xl font-semibold tabular-nums text-fg [overflow-wrap:anywhere]">{value}</span>
      {sub && <span className="muted text-xs [overflow-wrap:anywhere]">{sub}</span>}
    </div>
  );
}

export function Meter({ value, max, label, tone = 'nova' }: { value: number; max: number; label: string; tone?: 'nova' | 'signal' | 'ok' | 'warn' }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  const c = { nova: 'bg-nova-400', signal: 'bg-signal', ok: 'bg-emerald-400', warn: 'bg-amber-400' }[tone];
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-ink-300">{label}</span><span className="tabular-nums text-ink-400">{value} / {max}</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
        <div className={clsx('h-full rounded-full transition-[width] duration-700', c)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PageHeader({ title, kicker, children, actions }: { title: string; kicker?: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {kicker && <p className="label mb-1.5 text-nova-300">{kicker}</p>}
        <h1 className="text-2xl font-semibold text-fg md:text-[28px]">{title}</h1>
        {children && <div className="muted mt-1.5 max-w-3xl text-[15px]">{children}</div>}
      </div>
      {actions && <div className="flex min-w-0 max-w-full flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Toasts() {
  const items = useStore(toasts, (s) => s.items);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100%-2rem)] flex-col gap-2" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={clsx('rise pointer-events-auto flex items-start gap-2 rounded-xl border px-4 py-3 text-sm shadow-xl',
          t.kind === 'error' ? 'border-rose-500/40 bg-ink-850 text-rose-200 shadow-[var(--shadow-pop)]' : t.kind === 'info' ? 'border-cyan-400/30 bg-ink-850 text-cyan-100 shadow-[var(--shadow-pop)]' : 'border-emerald-500/30 bg-ink-850 text-emerald-200 shadow-[var(--shadow-pop)]')}>
          <Icon name={t.kind === 'error' ? 'alert' : t.kind === 'info' ? 'info' : 'check'} className="mt-0.5 shrink-0" />
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}

export const fmt = {
  pct: (v: number | null | undefined, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '-' : `${(v * 100).toFixed(d)}%`),
  date: (s?: string | null) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '-'),
  bytes: (n?: number | null) => (n ? (n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${(n / 1e3).toFixed(0)} kB`) : '-'),
};

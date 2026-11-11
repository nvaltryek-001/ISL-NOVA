// Accessible SVG charts (no chart library). Every chart has a text alternative.
import clsx from 'clsx';

const PALETTE = ['#a78bfa', '#22d3ee', '#818cf8', '#34d399', '#fbbf24', '#f472b6', '#60a5fa', '#c084fc', '#2dd4bf', '#fb923c', '#94a3b8', '#e879f9'];

export function HBars({ data, max, unit = '', label }: { data: { label: string; value: number; secondary?: number }[]; max?: number; unit?: string; label: string }) {
  const m = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <figure aria-label={label}>
      <ul className="space-y-2.5">
        {data.map((d, i) => (
          <li key={d.label} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm">
            <span className="truncate text-ink-300" title={d.label}>{d.label}</span>
            <span className="relative h-2.5 overflow-hidden rounded-full bg-ink-700/70">
              <span className="bar-grow absolute inset-y-0 left-0 rounded-full" style={{ width: `${(d.value / m) * 100}%`, background: PALETTE[i % PALETTE.length], animationDelay: `${i * 40}ms` }} />
              {d.secondary !== undefined && d.secondary > 0 && <span className="absolute inset-y-0 left-0 rounded-full bg-emerald-400" style={{ width: `${(d.secondary / m) * 100}%` }} />}
            </span>
            <span className="tabular-nums text-ink-200">{d.value}{unit}{d.secondary !== undefined && <span className="ml-1 text-emerald-300">/{d.secondary}</span>}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function Segmented({ parts, label }: { parts: { label: string; value: number; color: string }[]; label: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  return (
    <figure aria-label={label}>
      <div className="flex h-3 overflow-hidden rounded-full bg-ink-700" role="img" aria-label={parts.map((p) => `${p.label}: ${p.value}`).join(', ')}>
        {parts.filter((p) => p.value > 0).map((p) => <span key={p.label} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} />)}
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
        {parts.map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1.5 text-ink-300"><span className="size-2 rounded-full" style={{ background: p.color }} />{p.label}<b className="font-semibold tabular-nums text-fg">{p.value}</b></span>
        ))}
      </figcaption>
    </figure>
  );
}

export function LineChart({ series, height = 160, yMax = 1, label }: { series: { name: string; values: number[]; color?: string }[]; height?: number; yMax?: number; label: string }) {
  const W = 600;
  const n = Math.max(2, ...series.map((s) => s.values.length));
  const x = (i: number) => (i / (n - 1)) * (W - 40) + 30;
  const y = (v: number) => height - 20 - (v / yMax) * (height - 30);
  return (
    <figure aria-label={label}>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" role="img" aria-label={label}>
        {[0, 0.5, 1].map((t) => (
          <g key={t}><line x1={30} x2={W - 10} y1={y(t * yMax)} y2={y(t * yMax)} style={{ stroke: 'var(--color-ink-700)' }} /><text x={0} y={y(t * yMax) + 4} style={{ fill: 'var(--color-ink-400)' }} fontSize={10}>{(t * yMax).toFixed(yMax <= 1 ? 1 : 0)}</text></g>
        ))}
        {series.map((s, si) => (
          <polyline key={s.name} fill="none" stroke={s.color ?? PALETTE[si]} strokeWidth={2} points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')} />
        ))}
      </svg>
      <figcaption className="mt-1 flex gap-4 text-xs text-ink-300">{series.map((s, si) => <span key={s.name} className="inline-flex items-center gap-1.5"><span className="h-0.5 w-3" style={{ background: s.color ?? PALETTE[si] }} />{s.name}</span>)}</figcaption>
    </figure>
  );
}

export function Heatmap({ matrix, labels, label }: { matrix: number[][]; labels: string[]; label: string }) {
  const max = Math.max(1, ...matrix.flat());
  const cell = matrix.length > 30 ? 8 : matrix.length > 12 ? 14 : 28;
  return (
    <figure aria-label={label} className="overflow-auto">
      <div className="inline-grid gap-px" style={{ gridTemplateColumns: `auto repeat(${labels.length}, ${cell}px)` }}>
        <span />
        {labels.map((l) => <span key={l} className="truncate text-[9px] text-ink-400" style={{ writingMode: 'vertical-rl', height: 48 }}>{cell >= 14 ? l : ''}</span>)}
        {matrix.map((row, i) => [
          <span key={`l${i}`} className="pr-2 text-right text-[10px] text-ink-400">{cell >= 14 ? labels[i] : ''}</span>,
          ...row.map((v, j) => (
            <span key={`${i}-${j}`} title={`true ${labels[i]} → predicted ${labels[j]}: ${v}`}
              className={clsx('grid place-items-center text-[10px]', i === j ? 'text-on-accent' : 'text-fg')}
              style={{ width: cell, height: cell, background: v ? `rgba(${i === j ? '52,211,153' : '167,139,250'},${0.15 + 0.85 * (v / max)})` : 'var(--color-ink-800)' }}>
              {cell >= 28 && v ? v : ''}
            </span>
          )),
        ])}
      </div>
      <figcaption className="muted mt-2 text-xs">Rows: true class · columns: predicted class · diagonal = correct.</figcaption>
    </figure>
  );
}

export function ProbBars({ items }: { items: { label: string; sub?: string; p: number }[] }) {
  return (
    <ol className="space-y-2">
      {items.map((t, i) => (
        <li key={t.label + i} className="grid grid-cols-[1.5rem_1fr_3.5rem] items-center gap-2 text-sm">
          <span className="text-xs tabular-nums text-ink-400">{i + 1}</span>
          <span>
            <span className="flex justify-between"><span className={i === 0 ? 'font-medium text-fg' : 'text-ink-200'}>{t.label}</span><span className="text-xs text-ink-500">{t.sub}</span></span>
            <span className="mt-1 block h-1.5 rounded-full bg-ink-700"><span className="block h-full rounded-full" style={{ width: `${t.p * 100}%`, background: i === 0 ? 'var(--color-signal)' : 'var(--color-ink-500)' }} /></span>
          </span>
          <span className="text-right text-xs tabular-nums text-ink-300">{(t.p * 100).toFixed(1)}%</span>
        </li>
      ))}
    </ol>
  );
}

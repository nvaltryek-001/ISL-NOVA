import { useRef, useState } from 'react';
import { Button, Card, Empty, ErrorNote, Loading, Notice, PageHeader, StatusBadge, Table, fmt } from '../components/ui';
import { api } from '../lib/api';
import { useMutation, useQuery } from '../lib/query';
import { toast } from '../lib/store';

type Job = { id: number; filename: string; size_bytes: number; status: string; expires_at: string; created_at: string; result?: any };
const MAX_MB = 50;

export function VideoAnalysisPage() {
  const list = useQuery<Job[]>('/analysis/videos', { poll: 4000 });
  const [sel, setSel] = useState<number | null>(null);
  const job = useQuery<Job>(sel ? `/analysis/videos/${sel}` : null, { poll: 3000 });
  const input = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState('');

  const up = useMutation(async (f: File) => {
    const fd = new FormData();
    fd.append('file', f);
    return api<Job>('/analysis/videos', { form: fd });
  }, { invalidates: ['/analysis/videos'], onSuccess: (j) => { setSel(j.id); toast('Upload received, processing started'); } });
  const del = useMutation((id: number) => api(`/analysis/videos/${id}`, { method: 'DELETE' }), { invalidates: ['/analysis/videos'], onSuccess: () => { setSel(null); toast('Video and result deleted'); } });

  const pick = (f?: File) => {
    setErr('');
    if (!f) return;
    if (!/^video\/(mp4|webm|quicktime)$/.test(f.type)) { setErr('Choose an MP4, WebM or MOV video.'); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setErr(`The file is larger than ${MAX_MB} MB.`); return; }
    up.mutate(f);
  };

  const r = job.data?.result;
  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA Video Analysis" title="Video Analysis">
        Upload a short recording of a single sign. The server validates the file, extracts landmarks and runs the active model in sliding windows. Uploads are deleted automatically after 24 hours.
      </PageHeader>
      <Card>
        <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}
          className="grid-bg flex flex-col items-center gap-3 rounded-xl border border-dashed border-ink-600 p-10 text-center">
          <p className="font-medium text-fg">Drop a video here or choose a file</p>
          <p className="muted text-sm">MP4, WebM or MOV · up to {MAX_MB} MB · content type checked server-side</p>
          <input ref={input} type="file" accept="video/mp4,video/webm,video/quicktime" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} aria-label="Video file" />
          <Button variant="primary" icon="upload" loading={up.pending} onClick={() => input.current?.click()}>Choose video</Button>
          {err && <p className="text-sm text-rose-300" role="alert">{err}</p>}
          <ErrorNote error={up.error} />
        </div>
      </Card>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card title="Your uploads">
          {list.loading && !list.data ? <Loading /> : !list.data?.length ? <Empty icon="film" title="No uploads yet" /> : (
            <Table head={['File', 'Status', 'Expires', '']}>
              {list.data.map((j) => (
                <tr key={j.id} className={sel === j.id ? 'bg-ink-800' : ''}>
                  <td className="px-3 py-2"><button className="text-left hover:text-nova-300" onClick={() => setSel(j.id)}>{j.filename}</button><p className="muted text-xs">{fmt.bytes(j.size_bytes)}</p></td>
                  <td className="px-3 py-2"><StatusBadge status={j.status} /></td>
                  <td className="px-3 py-2 text-xs text-ink-400">{fmt.date(j.expires_at)}</td>
                  <td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" icon="trash" aria-label={`Delete ${j.filename}`} onClick={() => del.mutate(j.id)} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Result" action={job.data && <StatusBadge status={job.data.status} />}>
          {!sel ? <Empty title="Select an upload" /> : !r ? <Loading /> : (
            <div className="space-y-4 text-sm">
              <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[['Decodable', r.video.decodable ? 'Yes' : 'No'], ['Duration', `${r.video.duration_s ?? '-'} s`], ['Resolution', `${r.video.width}×${r.video.height}`], ['FPS', r.video.fps ? Number(r.video.fps).toFixed(1) : '-']].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-ink-800 p-3"><dt className="label">{k}</dt><dd className="mt-1 text-fg">{v}</dd></div>
                ))}
              </dl>
              {r.extractor && !r.extractor.available && <Notice tone="warn" title="Server-side landmark extractor is not configured">{r.extractor.reason}. Set ISL_NOVA_HAND_MODEL on the server to enable the frame timeline and inference.</Notice>}
              {r.timeline?.length > 0 && (
                <div>
                  <p className="label mb-2">Hand-tracking timeline ({r.timeline.length} frames)</p>
                  <div className="flex h-8 overflow-hidden rounded-md" role="img" aria-label="Per-frame hand detection">
                    {r.timeline.map((t: any) => <span key={t.frame} className="flex-1" style={{ background: t.left && t.right ? '#a78bfa' : t.left || t.right ? '#22d3ee' : 'var(--color-ink-700)' }} />)}
                  </div>
                  <p className="muted mt-1 text-xs">Violet: two hands · cyan: one hand · dark: none</p>
                </div>
              )}
              {r.model && !r.model.available && <Notice tone="warn" title="Model unavailable">No predictions were made: {r.model.reason}</Notice>}
              {r.predictions?.length > 0 && (
                <Table head={['Frames', 'State', 'Top prediction', 'p']}>
                  {r.predictions.map((p: any) => <tr key={p.start_frame}><td className="px-3 py-2 tabular-nums">{p.start_frame}-{p.end_frame}</td><td className="px-3 py-2"><StatusBadge status={p.state} /></td><td className="px-3 py-2">{p.top[0]?.label ?? '-'}</td><td className="px-3 py-2 tabular-nums">{p.top[0] ? (p.top[0].probability * 100).toFixed(1) + '%' : '-'}</td></tr>)}
                </Table>
              )}
              <div className="flex gap-2">
                <Button size="sm" icon="download" onClick={() => { const b = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `analysis-${sel}.json`; a.click(); }}>Export JSON</Button>
                <Button size="sm" variant="danger" icon="trash" onClick={() => del.mutate(sel)}>Delete now</Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

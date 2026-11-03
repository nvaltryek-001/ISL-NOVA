// Experimental 3D landmark viewer: records a real landmark sequence from the
// camera (or loads a JSON export) and plays it back with orbit, frame
// stepping and speed control. Pure canvas 2D projection, no 3D library.
import { useCallback, useEffect, useRef, useState } from 'react';
import { CameraStage } from '../components/CameraStage';
import { Badge, Button, Card, Empty, Notice, PageHeader, Select } from '../components/ui';
import type { Frame } from '../lib/features';
import { toast } from '../lib/store';

const HAND_EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
const POSE_EDGES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24]];

export function VizPage() {
  const [seq, setSeq] = useState<{ frames: Frame[]; aspect: number } | null>(null);
  const rec = useRef<Frame[] | null>(null);
  const aspect = useRef(4 / 3);
  const [recording, setRecording] = useState(false);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [yaw, setYaw] = useState(-0.5);
  const [pitch, setPitch] = useState(0.25);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);

  const onFrame = useCallback((f: Frame, a: number) => { if (rec.current) { rec.current.push(f); aspect.current = a; } }, []);
  const toggleRec = () => {
    if (!recording) { rec.current = []; setRecording(true); return; }
    const frames = rec.current ?? [];
    rec.current = null;
    setRecording(false);
    if (frames.length < 2) { toast('No landmarks captured', 'error'); return; }
    setSeq({ frames, aspect: aspect.current }); setI(0);
  };

  useEffect(() => {
    if (!playing || !seq) return;
    const t = setInterval(() => setI((x) => (x + 1) % seq.frames.length), 1000 / (30 * speed));
    return () => clearInterval(t);
  }, [playing, seq, speed]);

  useEffect(() => {
    const c = canvas.current;
    if (!c || !seq) return;
    const ctx = c.getContext('2d')!;
    const W = (c.width = c.clientWidth * devicePixelRatio);
    const H = (c.height = c.clientHeight * devicePixelRatio);
    ctx.clearRect(0, 0, W, H);
    const proj = (p: number[]) => {
      let x = (p[0] - 0.5) * seq.aspect;
      let y = p[1] - 0.5;
      let z = (p[2] ?? 0) * 1.5;
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      [x, z] = [x * cy + z * sy, -x * sy + z * cy];
      const cp = Math.cos(pitch), sp = Math.sin(pitch);
      [y, z] = [y * cp - z * sp, y * sp + z * cp];
      const s = Math.min(W, H) * 0.9 / (1.4 + z * 0.5);
      return [W / 2 + x * s, H / 2 + y * s];
    };
    // trajectory trails of both wrists
    for (const [key, col] of [['left', 'rgba(167,139,250,.35)'], ['right', 'rgba(34,211,238,.35)']] as const) {
      ctx.strokeStyle = col; ctx.lineWidth = 2 * devicePixelRatio; ctx.beginPath();
      let started = false;
      for (const f of seq.frames) { const h = f[key]; if (!h) { started = false; continue; } const [px, py] = proj(h[0]); if (started) ctx.lineTo(px, py); else { ctx.moveTo(px, py); started = true; } }
      ctx.stroke();
    }
    const f = seq.frames[i];
    const draw = (pts: number[][], edges: number[][], col: string) => {
      ctx.strokeStyle = col; ctx.lineWidth = 2.5 * devicePixelRatio; ctx.beginPath();
      for (const [a, b] of edges) { const [x1, y1] = proj(pts[a]); const [x2, y2] = proj(pts[b]); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); }
      ctx.stroke();
    };
    if (f.pose) draw(f.pose, POSE_EDGES, getComputedStyle(c).getPropertyValue('--color-ink-500').trim() || '#4a5578');
    if (f.left) draw(f.left, HAND_EDGES, '#a78bfa');
    if (f.right) draw(f.right, HAND_EDGES, '#22d3ee');
  }, [seq, i, yaw, pitch]);

  const load = async (file?: File) => {
    if (!file) return;
    try {
      const j = JSON.parse(await file.text());
      if (!Array.isArray(j.frames)) throw new Error('missing frames[]');
      setSeq({ frames: j.frames, aspect: Number(j.aspect) || 4 / 3 }); setI(0);
    } catch (e) { toast(`Could not load: ${(e as Error).message}`, 'error'); }
  };

  return (
    <div className="space-y-5">
      <PageHeader kicker="NOVA 3D Visualisation · experimental" title="3D Landmark Viewer">
        Inspect real hand and pose landmarks in 3D. Drag to orbit, step through frames and compare trajectories. MediaPipe depth (z) is relative and approximate.
      </PageHeader>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card title="Source">
          <CameraStage onFrame={onFrame} />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant={recording ? 'danger' : 'primary'} icon={recording ? 'stop' : 'record'} onClick={toggleRec}>{recording ? 'Stop & view' : 'Record sequence'}</Button>
            <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-ink-600 bg-ink-800 px-4 text-sm hover:bg-ink-700">Load JSON<input type="file" accept="application/json" className="sr-only" onChange={(e) => load(e.target.files?.[0])} /></label>
            {seq && <Button icon="download" onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(seq)], { type: 'application/json' })); a.download = 'landmarks.json'; a.click(); }}>Export</Button>}
          </div>
          <Notice title="Format">{'{ "aspect": 1.333, "frames": [{ "left": [[x,y,z]×21] | null, "right": …, "pose": [[x,y,z,v]×33] | null }] }'}</Notice>
        </Card>
        <Card title="Viewer" action={seq && <Badge>{i + 1} / {seq.frames.length}</Badge>}>
          {!seq ? <Empty icon="cube" title="No sequence loaded">Record a few seconds of signing or load a landmark JSON file.</Empty> : (
            <>
              <canvas ref={canvas} className="aspect-[4/3] w-full cursor-grab rounded-xl bg-ink-950 active:cursor-grabbing" aria-label="3D landmark rendering"
                onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY }; (e.target as Element).setPointerCapture(e.pointerId); }}
                onPointerMove={(e) => { if (!drag.current) return; setYaw((y) => y + (e.clientX - drag.current!.x) * 0.01); setPitch((p) => Math.max(-1.2, Math.min(1.2, p + (e.clientY - drag.current!.y) * 0.01))); drag.current = { x: e.clientX, y: e.clientY }; }}
                onPointerUp={() => { drag.current = null; }} />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button size="sm" icon="chevron" className="[&>svg]:rotate-180" aria-label="Previous frame" onClick={() => setI((x) => Math.max(0, x - 1))} />
                <Button size="sm" variant="primary" icon={playing ? 'pause' : 'play'} onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</Button>
                <Button size="sm" icon="chevron" aria-label="Next frame" onClick={() => setI((x) => Math.min(seq.frames.length - 1, x + 1))} />
                <input type="range" min={0} max={seq.frames.length - 1} value={i} onChange={(e) => setI(Number(e.target.value))} className="flex-1 accent-nova-500" aria-label="Frame" />
                <Select aria-label="Speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="h-8 w-auto py-0 text-xs">{[0.25, 0.5, 1, 2].map((s) => <option key={s} value={s}>{s}×</option>)}</Select>
                <Button size="sm" variant="ghost" onClick={() => { setYaw(0); setPitch(0); }}>Front view</Button>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

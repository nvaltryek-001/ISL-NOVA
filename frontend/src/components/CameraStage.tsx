// Camera + landmark pipeline shared by Live Recognition, Recording Studio and Kiosk.
import { useEffect, useRef, useState } from 'react';
import type { Frame } from '../lib/features';
import { type CameraState, drawOverlay, type Extractor, listCameras, loadExtractor, openCamera } from '../lib/landmarks';
import { Icon } from './icons';
import { Badge, Button, Select } from './ui';

export type StageApi = { frames: React.MutableRefObject<Frame[]>; aspect: number; extractor: 'loading' | 'ready' | 'unavailable' };

export function CameraStage({ onFrame, showPose = true, keep = 90, large, onState, recordStream }:
  { onFrame?: (f: Frame, aspect: number) => void; showPose?: boolean; keep?: number; large?: boolean; onState?: (s: CameraState, ex: StageApi['extractor']) => void; recordStream?: (s: MediaStream | null) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const ex = useRef<Extractor | null>(null);
  const raf = useRef(0);
  const [state, setState] = useState<CameraState>('idle');
  const [exState, setExState] = useState<StageApi['extractor']>('loading');
  const [exError, setExError] = useState('');
  const [cams, setCams] = useState<MediaDeviceInfo[]>([]);
  const [camId, setCamId] = useState<string>('');
  const [fps, setFps] = useState(0);
  const [err, setErr] = useState('');
  const frames = useRef<Frame[]>([]);
  const [tracking, setTracking] = useState({ l: false, r: false, p: false });

  useEffect(() => { onState?.(state, exState); }, [state, exState, onState]);

  const stop = () => {
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    recordStream?.(null);
    if (video.current) video.current.srcObject = null;
    setState('idle');
  };

  const start = async (id = camId) => {
    setErr('');
    setState('requesting');
    try {
      stop();
      setState('requesting');
      const s = await openCamera(id || undefined);
      stream.current = s;
      recordStream?.(s);
      const v = video.current!;
      v.srcObject = s;
      await v.play();
      setState('live');
      setCams(await listCameras());
      loadExtractor(showPose).then((e) => { ex.current = e; setExState('ready'); })
        .catch((e) => { setExState('unavailable'); setExError(String(e?.message ?? e)); });
      loop();
    } catch (e) {
      setState(((e as { state?: CameraState }).state) ?? 'error');
      setErr((e as Error).message);
    }
  };

  const loop = () => {
    let last = performance.now();
    let count = 0;
    const tick = () => {
      const v = video.current;
      if (!v || !stream.current) return;
      if (ex.current && v.readyState >= 2) {
        const now = performance.now();
        try {
          const f = ex.current.detect(v, now);
          frames.current.push(f);
          if (frames.current.length > keep) frames.current.shift();
          const c = canvas.current;
          if (c) {
            if (c.width !== v.videoWidth) { c.width = v.videoWidth; c.height = v.videoHeight; }
            drawOverlay(c.getContext('2d')!, f, c.width, c.height, showPose);
          }
          setTracking({ l: !!f.left, r: !!f.right, p: !!f.pose });
          onFrame?.(f, v.videoWidth / (v.videoHeight || 1));
        } catch { /* skip frame */ }
        count++;
        if (now - last > 1000) { setFps(Math.round((count * 1000) / (now - last))); count = 0; last = now; }
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  useEffect(() => () => stop(), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-3">
      <div className={`relative overflow-hidden rounded-2xl border border-ink-700 bg-ink-950 ${large ? 'aspect-[4/3] md:aspect-video' : 'aspect-[4/3]'}`}>
        <video ref={video} playsInline muted className="absolute inset-0 size-full -scale-x-100 object-cover" aria-label="Camera preview (mirrored)" />
        <canvas ref={canvas} className="pointer-events-none absolute inset-0 size-full -scale-x-100 object-cover" aria-hidden />
        {state !== 'live' && (
          <div className="grid-bg absolute inset-0 grid place-items-center p-6 text-center">
            <div className="max-w-sm space-y-3">
              <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-ink-800 text-nova-300 ring-1 ring-ink-600"><Icon name="camera" size={26} /></div>
              {state === 'idle' && <><p className="font-medium">Camera is off</p><p className="muted text-sm">Video stays on this device. Only landmark coordinates are sent for recognition.</p><Button variant="primary" icon="camera" onClick={() => start()}>Start camera</Button></>}
              {state === 'requesting' && <p className="muted text-sm" role="status">Waiting for camera permission…</p>}
              {state === 'denied' && <><p className="font-medium text-rose-200">Camera permission denied</p><p className="muted text-sm">Allow camera access in your browser's site settings, then try again.</p><Button onClick={() => start()} icon="refresh">Try again</Button></>}
              {(state === 'unsupported' || state === 'error') && <><p className="font-medium text-rose-200">Camera unavailable</p><p className="muted text-sm">{err || 'No camera could be opened.'}</p><Button onClick={() => start()} icon="refresh">Retry</Button></>}
            </div>
          </div>
        )}
        {state === 'live' && (
          <div className="absolute left-3 top-3 flex flex-wrap gap-1.5">
            <Badge tone="bad"><span className="live-dot size-1.5 rounded-full bg-rose-400" />LIVE</Badge>
            <Badge tone={tracking.l ? 'nova' : 'neutral'}>L hand</Badge>
            <Badge tone={tracking.r ? 'signal' : 'neutral'}>R hand</Badge>
            {showPose && <Badge tone={tracking.p ? 'ok' : 'neutral'}>Pose</Badge>}
            {exState === 'ready' && <Badge>{fps} fps</Badge>}
          </div>
        )}
        {state === 'live' && exState !== 'ready' && (
          <div className="absolute inset-x-3 bottom-3 rounded-xl border border-ink-600 bg-ink-900/90 p-3 text-sm backdrop-blur" role="status">
            {exState === 'loading' ? 'Loading hand-tracking models…' : <><b className="text-amber-200">Landmark extractor unavailable.</b> <span className="muted">MediaPipe could not be loaded ({exError.slice(0, 120)}). Recognition needs it; check network access to cdn.jsdelivr.net and storage.googleapis.com.</span></>}
          </div>
        )}
      </div>
      {state === 'live' && (
        <div className="flex flex-wrap items-center gap-2">
          {cams.length > 1 && (
            <Select aria-label="Camera" value={camId} onChange={(e) => { setCamId(e.target.value); start(e.target.value); }} className="w-auto">
              <option value="">Default camera</option>
              {cams.map((c, i) => <option key={c.deviceId} value={c.deviceId}>{c.label || `Camera ${i + 1}`}</option>)}
            </Select>
          )}
          <Button size="sm" variant="ghost" icon="stop" onClick={stop}>Stop camera</Button>
        </div>
      )}
    </div>
  );
}

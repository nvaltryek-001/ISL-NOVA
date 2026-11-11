// Plays a reference landmark sequence (from /practice/reference/{id}) as a looping skeleton.
// Mirrored like the camera preview so learners can copy it like a mirror.
import { useEffect, useRef, useState } from 'react';
import type { Frame } from '../lib/features';
import { drawOverlay } from '../lib/landmarks';
import { useQuery } from '../lib/query';
import { useT } from '../i18n';

export type Reference = { sign_id: string; label: string; fps: number; frames: Frame[]; verification_status: string | null; attribution: string };

export function SignAnimation({ signId, size = 'md', speed = 1, onLoaded }: { signId: string; size?: 'sm' | 'md' | 'lg'; speed?: number; onLoaded?: (r: Reference) => void }) {
  const t = useT();
  const { data, error } = useQuery<Reference>(signId ? `/practice/reference/${signId}` : null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [playing, setPlaying] = useState(true);

  useEffect(() => { if (data) onLoaded?.(data); }, [data, onLoaded]);
  useEffect(() => {
    if (!data || !canvas.current) return;
    const c = canvas.current;
    const ctx = c.getContext('2d')!;
    let i = 0;
    let raf = 0;
    let last = 0;
    const step = 1000 / (data.fps * speed);
    const tick = (now: number) => {
      if (playing && now - last >= step) {
        last = now;
        drawOverlay(ctx, data.frames[i % data.frames.length], c.width, c.height, true);
        i += 1;
        if (i >= data.frames.length + 6) i = 0; // short pause at the end of each loop
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [data, playing, speed]);

  const h = size === 'lg' ? 'h-80 md:h-96' : size === 'sm' ? 'h-40' : 'h-64';
  if (error) return <div className={`grid ${h} place-items-center rounded-2xl border border-ink-700 bg-ink-900 p-4 text-center text-sm text-ink-300`}>{error.status === 503 ? t('Reference animations are not installed on this server.') : t('No reference animation for this sign.')}</div>;
  return (
    <figure className="space-y-1.5">
      <div className={`relative ${h} overflow-hidden rounded-2xl border border-ink-700 bg-ink-950`}>
        <canvas ref={canvas} width={640} height={480} className="size-full -scale-x-100 object-contain" role="img"
          aria-label={data ? `${t('Reference animation')}: ${data.label}` : t('Loading')} />
        <button className="absolute bottom-2 right-2 rounded-lg bg-ink-900/80 px-2 py-1 text-xs text-ink-200" onClick={() => setPlaying(!playing)}>
          {playing ? t('Pause') : t('Play')}
        </button>
      </div>
      <figcaption className="muted text-xs">{t('Landmarks from an INCLUDE recording (CC BY 4.0), mirrored.')}</figcaption>
    </figure>
  );
}

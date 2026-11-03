// In-browser landmark extraction with MediaPipe Tasks Vision, loaded lazily
// from jsDelivr (pinned version). Frames are processed UNMIRRORED so
// handedness matches the Python extractor (contract isl-nova-fc-1.0.0); the
// preview is mirrored with CSS only.
import type { Frame } from './features';

export const MEDIAPIPE_VERSION = '0.10.14';
const CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`;
export const HAND_MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
export const POSE_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

export type Extractor = { detect: (v: HTMLVideoElement, ts: number) => Frame; close: () => void; withPose: boolean };

let loading: Promise<Extractor> | null = null;

export function loadExtractor(withPose = true): Promise<Extractor> {
  if (!loading) loading = create(withPose).catch((e) => { loading = null; throw e; });
  return loading;
}

async function create(withPose: boolean): Promise<Extractor> {
  const url = `${CDN}/vision_bundle.mjs`;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vision: any = await import(/* @vite-ignore */ url);
  const files = await vision.FilesetResolver.forVisionTasks(`${CDN}/wasm`);
  const hands = await vision.HandLandmarker.createFromOptions(files, {
    baseOptions: { modelAssetPath: HAND_MODEL, delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2,
    minHandDetectionConfidence: 0.5, minTrackingConfidence: 0.5,
  });
  let pose: any = null;
  if (withPose) {
    try {
      pose = await vision.PoseLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: POSE_MODEL, delegate: 'GPU' }, runningMode: 'VIDEO', numPoses: 1,
      });
    } catch { pose = null; }
  }
  return {
    withPose: !!pose,
    detect(v, ts) {
      const r = hands.detectForVideo(v, ts);
      const f: Frame = { left: null, right: null, pose: null };
      const hd = r.handedness ?? r.handednesses ?? [];
      (r.landmarks ?? []).forEach((lms: { x: number; y: number; z: number }[], i: number) => {
        const side = String(hd[i]?.[0]?.categoryName ?? '').toLowerCase();
        if ((side === 'left' || side === 'right') && !f[side]) f[side] = lms.map((p) => [p.x, p.y, p.z]);
      });
      if (pose) {
        const pr = pose.detectForVideo(v, ts);
        const p = pr.landmarks?.[0];
        if (p) f.pose = p.map((q: { x: number; y: number; z: number; visibility?: number }) => [q.x, q.y, q.z, q.visibility ?? 1]);
      }
      return f;
    },
    close() { hands.close?.(); pose?.close?.(); },
  };
}

export type CameraState = 'idle' | 'requesting' | 'live' | 'denied' | 'unsupported' | 'error';

export async function listCameras(): Promise<MediaDeviceInfo[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
}

export async function openCamera(deviceId?: string): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) throw Object.assign(new Error('Camera API not supported in this browser'), { state: 'unsupported' });
  try {
    return await navigator.mediaDevices.getUserMedia({
      video: { deviceId: deviceId ? { exact: deviceId } : undefined, width: { ideal: 960 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
      audio: false,
    });
  } catch (e) {
    const n = (e as DOMException).name;
    const state = n === 'NotAllowedError' || n === 'SecurityError' ? 'denied' : 'error';
    throw Object.assign(new Error((e as Error).message || n), { state });
  }
}

const HAND_EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
const POSE_EDGES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24]];

export function drawOverlay(ctx: CanvasRenderingContext2D, f: Frame, w: number, h: number, showPose = true) {
  ctx.clearRect(0, 0, w, h);
  const line = (pts: number[][], edges: number[][], color: string, width: number) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    for (const [a, b] of edges) { ctx.moveTo(pts[a][0] * w, pts[a][1] * h); ctx.lineTo(pts[b][0] * w, pts[b][1] * h); }
    ctx.stroke();
  };
  if (showPose && f.pose) line(f.pose, POSE_EDGES, 'rgba(129,140,248,.55)', 3);
  for (const [hand, color] of [[f.left, '#a78bfa'], [f.right, '#22d3ee']] as const) {
    if (!hand) continue;
    line(hand, HAND_EDGES, color, 2.5);
    ctx.fillStyle = '#fff';
    for (const p of hand) { ctx.beginPath(); ctx.arc(p[0] * w, p[1] * h, 2.6, 0, Math.PI * 2); ctx.fill(); }
  }
}

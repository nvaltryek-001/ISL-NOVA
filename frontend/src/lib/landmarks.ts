// In-browser landmark extraction with MediaPipe Tasks Vision, loaded lazily
// from jsDelivr (pinned version). Frames are processed UNMIRRORED so
// handedness matches the Python extractor (contract isl-nova-fc-1.0.0); the
// preview is mirrored with CSS only.
import { FACE_KEEP, type Frame } from './features';

export const MEDIAPIPE_VERSION = '0.10.14';
const CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`;
export const HAND_MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
export const POSE_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
export const FACE_MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

export type Extractor = { detect: (v: HTMLVideoElement, ts: number) => Frame; close: () => void; withPose: boolean; withFace: boolean; delegate: string };

export type Delegate = 'GPU' | 'CPU';
const loading = new Map<string, Promise<Extractor>>();

/** Load (once per delegate) the MediaPipe hand + pose (+ face, for contract 2.0.0 models) landmarkers.
 *  'GPU' falls back to 'CPU' if WebGL fails. */
export function loadExtractor(withPose = true, delegate: Delegate = preferredDelegate(), withFace = false): Promise<Extractor> {
  const key = `${withPose}:${delegate}:${withFace}`;
  let p = loading.get(key);
  if (!p) {
    p = create(withPose, delegate, withFace).catch((e) => { loading.delete(key); throw e; });
    loading.set(key, p);
  }
  return p;
}

// Some machines (software WebGL, weak integrated GPUs, CI) run the GPU delegate far slower than WASM.
// When the camera stage measures that, it switches to CPU and remembers the choice for this browser.
const PREF_KEY = 'isl-nova.mediapipe-delegate';
export function preferredDelegate(): Delegate {
  try { return localStorage.getItem(PREF_KEY) === 'CPU' ? 'CPU' : 'GPU'; } catch { return 'GPU'; }
}
export function rememberDelegate(d: Delegate) {
  try { localStorage.setItem(PREF_KEY, d); } catch { /* storage unavailable */ }
}

async function create(withPose: boolean, preferred: Delegate, withFace: boolean): Promise<Extractor> {
  const url = `${CDN}/vision_bundle.mjs`;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vision: any = await import(/* @vite-ignore */ url);
  const files = await vision.FilesetResolver.forVisionTasks(`${CDN}/wasm`);
  // GPU (WebGL) is usually fastest; fall back to CPU (WASM) where WebGL is unavailable.
  const make = async (Task: any, opts: Record<string, unknown>, asset: string) => {
    if (preferred === 'GPU') {
      try { return { task: await Task.createFromOptions(files, { ...opts, baseOptions: { modelAssetPath: asset, delegate: 'GPU' } }), delegate: 'GPU' }; }
      catch { /* fall through to CPU */ }
    }
    return { task: await Task.createFromOptions(files, { ...opts, baseOptions: { modelAssetPath: asset, delegate: 'CPU' } }), delegate: 'CPU' };
  };
  const h = await make(vision.HandLandmarker, { runningMode: 'VIDEO', numHands: 2, minHandDetectionConfidence: 0.5, minTrackingConfidence: 0.5 }, HAND_MODEL);
  const hands = h.task;
  let pose: any = null;
  if (withPose) {
    try {
      pose = (await make(vision.PoseLandmarker, { runningMode: 'VIDEO', numPoses: 1 }, POSE_MODEL)).task;
    } catch { pose = null; }
  }
  let face: any = null;
  if (withFace) {  // non-manual features: only when the active model was trained with them
    try {
      face = (await make(vision.FaceLandmarker, { runningMode: 'VIDEO', numFaces: 1 }, FACE_MODEL)).task;
    } catch { face = null; }
  }
  return {
    withPose: !!pose,
    withFace: !!face,
    delegate: h.delegate,
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
      if (face) {
        const fr = face.detectForVideo(v, ts);
        const pts = fr.faceLandmarks?.[0];
        if (pts) f.face = FACE_KEEP.map((k) => [pts[k].x, pts[k].y, pts[k].z]);
      }
      return f;
    },
    close() { hands.close?.(); pose?.close?.(); face?.close?.(); },
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

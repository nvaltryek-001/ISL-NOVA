// TypeScript port of ml/isl_nova_ml/features.py - contract isl-nova-fc-1.0.0.
// Kept numerically identical to the Python reference; verified by
// tests/features.test.ts against tests/fixtures/feature_parity.json.

export const CONTRACT = 'isl-nova-fc-1.0.0';
export const SEQ = 32;
export const DIM = 204;
const STATIC = DIM - 6;
const MIN_HAND_RATIO = 0.25;
const MIN_FRAMES = 8;
const EPS = 1e-6;
const POSE_KEEP = [0, 11, 12, 13, 14, 15, 16, 23, 24];
const TIPS = [4, 8, 12, 16, 20];
const JOINTS: [number, number, number][] = [
  [0, 1, 2], [1, 2, 3], [2, 3, 4], [0, 5, 6], [5, 6, 7], [6, 7, 8], [0, 9, 10], [9, 10, 11], [10, 11, 12],
  [0, 13, 14], [13, 14, 15], [14, 15, 16], [0, 17, 18], [17, 18, 19], [18, 19, 20],
];
const PRES = 195;
const WRISTS = 126;
// [start, end, gate] gate: L | R | P | LR
const SEGMENTS: [number, number, string][] = [
  [0, 63, 'L'], [63, 126, 'R'], [126, 129, 'L'], [129, 132, 'R'], [132, 159, 'P'], [159, 165, 'LR'],
  [165, 180, 'L'], [180, 195, 'R'],
];

export type Pt = number[];
export type Frame = { left: Pt[] | null; right: Pt[] | null; pose: Pt[] | null };
export type FeatureResult = { features: number[][]; rawFrames: number; handRatio: number; poseRatio: number; status: 'ok' | 'insufficient_input'; reasons: string[] };

type V3 = [number, number, number];
const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const norm = (a: V3) => Math.hypot(a[0], a[1], a[2]);

function parse(arr: Pt[] | null, n: number, aspect: number): V3[] | null {
  if (!arr) return null;
  if (arr.length < n) throw new Error(`landmark array must have ${n} points`);
  return arr.slice(0, n).map((p) => [p[0] * aspect, p[1], p[2]] as V3);
}

function median(xs: number[]) {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

const handScale = (h: V3[]) => Math.max(norm(sub(h[9], h[0])), EPS);

function bodyFrame(hl: (V3[] | null)[], hr: (V3[] | null)[], po: (V3[] | null)[]): [V3, number] {
  const mids: V3[] = [];
  const widths: number[] = [];
  for (const p of po) if (p) {
    mids.push([(p[11][0] + p[12][0]) / 2, (p[11][1] + p[12][1]) / 2, (p[11][2] + p[12][2]) / 2]);
    widths.push(norm(sub(p[11], p[12])));
  }
  if (mids.length) return [[0, 1, 2].map((k) => median(mids.map((m) => m[k]))) as V3, Math.max(median(widths), EPS)];
  const hands = [...hl, ...hr].filter(Boolean) as V3[][];
  if (!hands.length) return [[0, 0, 0], 1];
  const mean = [0, 1, 2].map((k) => hands.reduce((s, h) => s + h[0][k], 0) / hands.length) as V3;
  return [mean, Math.max(median(hands.map(handScale)) * 3, EPS)];
}

function angles(h: V3[]) {
  return JOINTS.map(([a, b, c]) => {
    const v1 = sub(h[a], h[b]);
    const v2 = sub(h[c], h[b]);
    const cos = (v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]) / Math.max(norm(v1) * norm(v2), EPS);
    return Math.acos(Math.min(1, Math.max(-1, cos))) / Math.PI;
  });
}

function frameStatic(lh: V3[] | null, rh: V3[] | null, po: V3[] | null, o: V3, s: number) {
  const v = new Float64Array(STATIC);
  let off = 0;
  for (const h of [lh, rh]) {
    if (h) { const sc = handScale(h); h.forEach((p, i) => { for (let k = 0; k < 3; k++) v[off + i * 3 + k] = (p[k] - h[0][k]) / sc; }); }
    off += 63;
  }
  for (const h of [lh, rh]) {
    if (h) for (let k = 0; k < 3; k++) v[off + k] = (h[0][k] - o[k]) / s;
    off += 3;
  }
  if (po) POSE_KEEP.forEach((idx, i) => { for (let k = 0; k < 3; k++) v[off + i * 3 + k] = (po[idx][k] - o[k]) / s; });
  off += 27;
  if (lh && rh) {
    v[off] = norm(sub(lh[0], rh[0])) / s;
    TIPS.forEach((t, k) => { v[off + 1 + k] = norm(sub(lh[t], rh[t])) / s; });
  }
  off += 6;
  for (const h of [lh, rh]) {
    if (h) angles(h).forEach((a, i) => { v[off + i] = a; });
    off += 15;
  }
  const pres: [boolean, boolean, boolean] = [!!lh, !!rh, !!po];
  pres.forEach((p, i) => { v[off + i] = p ? 1 : 0; });
  return { v, pres };
}

const ok = (p: [boolean, boolean, boolean], g: string) => (g === 'L' ? p[0] : g === 'R' ? p[1] : g === 'P' ? p[2] : p[0] && p[1]);

export function extractFeatures(frames: Frame[], aspect = 1): FeatureResult {
  const n = frames.length;
  const zeros = () => Array.from({ length: SEQ }, () => new Array(DIM).fill(0));
  if (!n) return { features: zeros(), rawFrames: 0, handRatio: 0, poseRatio: 0, status: 'insufficient_input', reasons: ['no frames'] };
  const hl = frames.map((f) => parse(f.left, 21, aspect));
  const hr = frames.map((f) => parse(f.right, 21, aspect));
  const po = frames.map((f) => parse(f.pose, 33, aspect));
  const [o, s] = bodyFrame(hl, hr, po);
  const st = frames.map((_, i) => frameStatic(hl[i], hr[i], po[i], o, s));
  const handRatio = st.filter((x) => x.pres[0] || x.pres[1]).length / n;
  const poseRatio = st.filter((x) => x.pres[2]).length / n;
  const out = zeros();
  for (let t = 0; t < SEQ; t++) {
    const pos = n > 1 ? (t * (n - 1)) / (SEQ - 1) : 0;
    const i0 = Math.floor(pos);
    const i1 = Math.min(i0 + 1, n - 1);
    const w = pos - i0;
    const a = st[i0];
    const b = st[i1];
    for (const [lo, hi, g] of SEGMENTS) {
      const o0 = ok(a.pres, g);
      const o1 = ok(b.pres, g);
      for (let k = lo; k < hi; k++) out[t][k] = o0 && o1 ? (1 - w) * a.v[k] + w * b.v[k] : o0 ? a.v[k] : o1 ? b.v[k] : 0;
    }
    for (let k = 0; k < 3; k++) out[t][PRES + k] = a.pres[k] || b.pres[k] ? 1 : 0;
  }
  for (let t = 1; t < SEQ; t++) for (const [side, k] of [[0, 0], [1, 3]]) {
    if (out[t][PRES + side] && out[t - 1][PRES + side]) for (let j = 0; j < 3; j++) out[t][STATIC + k + j] = out[t][WRISTS + k + j] - out[t - 1][WRISTS + k + j];
  }
  const f32 = out.map((r) => Array.from(Float32Array.from(r)));
  const reasons: string[] = [];
  if (n < MIN_FRAMES) reasons.push(`only ${n} frames (minimum ${MIN_FRAMES})`);
  if (handRatio < MIN_HAND_RATIO) reasons.push(`hands visible in ${Math.round(handRatio * 100)}% of frames (minimum ${MIN_HAND_RATIO * 100}%)`);
  return { features: f32, rawFrames: n, handRatio, poseRatio, status: reasons.length ? 'insufficient_input' : 'ok', reasons };
}

/** Client-side quality summary used before sending a window to the server. */
export function windowQuality(frames: Frame[]) {
  const n = frames.length || 1;
  const hands = frames.filter((f) => f.left || f.right).length / n;
  const both = frames.filter((f) => f.left && f.right).length / n;
  const pose = frames.filter((f) => f.pose).length / n;
  return { hands, both, pose, frames: frames.length };
}

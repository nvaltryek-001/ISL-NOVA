// In-browser inference for LSTM / GRU models exported by ml/isl_nova_ml/export_web.py.
// Used when the server cannot be reached (offline PWA) or when the user chooses
// on-device recognition. Same maths as the Python models (float32 weights);
// verified against Python probabilities in tests/webModel.test.ts.
export type WebHeader = {
  format: string; model_id: string; kind: 'lstm' | 'gru' | 'bilstm_attn'; D: number; C: number; H: number; temperature: number;
  tau: number; margin: number; contract: string; classes: { index: number; sign_id: string; label: string }[];
  tensors: { name: string; shape: number[]; offset: number; length: number }[]; synthetic: boolean;
  open_set_detector?: Detector | null;
};
type Detector = { features: string[]; mu: number[]; sd: number[]; coef: number[]; intercept: number; t_recognized: number; t_uncertain: number };

/** Same features as isl_nova_ml.openset.detector_features (vocabulary columns only). */
export function detectorScore(det: Detector, p: Float64Array, known: number[], other: number): number {
  const K = known.map((i) => p[i]);
  const s = [...K].sort((a, b) => b - a);
  const tot = K.reduce((a, b) => a + b, 0) || 1e-12;
  const ent = K.reduce((a, v) => { const q = v / tot; return a + q * Math.log(Math.max(q, 1e-12)); }, 0);
  const f: Record<string, number> = { maxprob: s[0], margin: s[0] - (s[1] ?? 0), entropy: ent, other: other >= 0 ? -p[other] : 0 };
  return det.features.reduce((acc, n, j) => acc + ((f[n] - det.mu[j]) / det.sd[j]) * det.coef[j], det.intercept);
}
type Tensors = Record<string, Float32Array>;

const sig = (x: number) => 0.5 * (1 + Math.tanh(0.5 * x));

function softmaxT(z: Float64Array, temperature: number): Float64Array {
  const out = new Float64Array(z.length);
  let mx = -Infinity;
  for (let j = 0; j < z.length; j++) { out[j] = z[j] / temperature; mx = Math.max(mx, out[j]); }
  let tot = 0;
  for (let j = 0; j < z.length; j++) { out[j] = Math.exp(out[j] - mx); tot += out[j]; }
  for (let j = 0; j < z.length; j++) out[j] /= tot;
  return out;
}

export class WebModel {
  constructor(public header: WebHeader, private t: Tensors) {}

  static fromBuffers(header: WebHeader, weights: ArrayBuffer): WebModel {
    if (header.format !== 'isl-nova-web-1') throw new Error(`unsupported web model format ${header.format}`);
    const all = new Float32Array(weights);
    const t: Tensors = {};
    for (const x of header.tensors) t[x.name] = all.subarray(x.offset, x.offset + x.length);
    return new WebModel(header, t);
  }

  static fromArrays(header: Omit<WebHeader, 'tensors'>, arrays: Record<string, number[]>): WebModel {
    const t: Tensors = {};
    for (const [k, v] of Object.entries(arrays)) t[k] = Float32Array.from(v);
    return new WebModel({ ...header, tensors: [] } as WebHeader, t);
  }

  /** One LSTM direction over normalised inputs: returns h_t for every step. */
  private lstm(xs: Float64Array[], Wx: Float32Array, Wh: Float32Array, b: Float32Array): Float64Array[] {
    const { D, H } = this.header;
    let h = new Float64Array(H);
    let c = new Float64Array(H);
    const out: Float64Array[] = [];
    for (const x of xs) {
      const hn = new Float64Array(H);
      const cn = new Float64Array(H);
      const z = new Float64Array(4 * H);
      for (let j = 0; j < 4 * H; j++) {
        let s = b[j];
        for (let d = 0; d < D; d++) s += x[d] * Wx[d * 4 * H + j];
        for (let k = 0; k < H; k++) s += h[k] * Wh[k * 4 * H + j];
        z[j] = s;
      }
      for (let k = 0; k < H; k++) {
        const i = sig(z[k]), f = sig(z[H + k]), o = sig(z[2 * H + k]), g = Math.tanh(z[3 * H + k]);
        cn[k] = f * c[k] + i * g;
        hn[k] = o * Math.tanh(cn[k]);
      }
      h = hn; c = cn;
      out.push(h);
    }
    return out;
  }

  private bilstmAttnLogits(X: number[][]): Float64Array {
    const { D, H, C } = this.header;
    const t = this.t;
    const xs = X.map((row) => Float64Array.from({ length: D }, (_, d) => (row[d] - t.norm_mean[d]) / t.norm_std[d]));
    const hf = this.lstm(xs, t.Wfx, t.Wfh, t.bf);
    const hr = this.lstm([...xs].reverse(), t.Wrx, t.Wrh, t.br).reverse();
    const T = xs.length || 1;
    const A = t.batt.length;
    const hs = hf.map((f, i) => { const v = new Float64Array(2 * H); v.set(f, 0); v.set(hr[i], H); return v; });
    const e = hs.map((v) => {
      let s = 0;
      for (let a = 0; a < A; a++) {
        let u = t.batt[a];
        for (let k = 0; k < 2 * H; k++) u += v[k] * t.Watt[k * A + a];
        s += Math.tanh(u) * t.vatt[a];
      }
      return s;
    });
    const mx = Math.max(...e);
    const w = e.map((x) => Math.exp(x - mx));
    const ws = w.reduce((a, b2) => a + b2, 0);
    const pooled = new Float64Array(4 * H);
    hs.forEach((v, i) => { for (let k = 0; k < 2 * H; k++) { pooled[k] += (w[i] / ws) * v[k]; pooled[2 * H + k] += v[k] / T; } });
    const logits = new Float64Array(C);
    for (let j = 0; j < C; j++) {
      let s = t.bhead[j];
      for (let k = 0; k < 4 * H; k++) s += pooled[k] * t.Whead[k * C + j];
      logits[j] = s;
    }
    return logits;
  }

  /** X: [T][D] features (one sequence) -> calibrated class probabilities. */
  predictProba(X: number[][]): Float64Array {
    const { D, H, C, kind, temperature } = this.header;
    if (kind === 'bilstm_attn') return softmaxT(this.bilstmAttnLogits(X), temperature);
    const { Wx, Wh, b, Wo, bo, norm_mean: mu, norm_std: sd } = this.t;
    const G = kind === 'lstm' ? 4 : 3;
    let h = new Float64Array(H);
    let c = new Float64Array(H);
    const sum = new Float64Array(H);
    const x = new Float64Array(D);
    const z = new Float64Array(G * H);
    const hu = new Float64Array(G * H);
    for (const row of X) {
      for (let d = 0; d < D; d++) x[d] = (row[d] - mu[d]) / sd[d];
      for (let j = 0; j < G * H; j++) {
        let s = kind === 'lstm' ? b[j] : b[j];
        for (let d = 0; d < D; d++) s += x[d] * Wx[d * G * H + j];
        z[j] = s;
        let u = 0;
        for (let k = 0; k < H; k++) u += h[k] * Wh[k * G * H + j];
        hu[j] = u;
      }
      const hn = new Float64Array(H);
      const cn = new Float64Array(H);
      if (kind === 'lstm') {
        for (let k = 0; k < H; k++) {
          const i = sig(z[k] + hu[k]);
          const f = sig(z[H + k] + hu[H + k]);
          const o = sig(z[2 * H + k] + hu[2 * H + k]);
          const g = Math.tanh(z[3 * H + k] + hu[3 * H + k]);
          cn[k] = f * c[k] + i * g;
          hn[k] = o * Math.tanh(cn[k]);
        }
      } else {
        const bhn = this.t.bhn;
        for (let k = 0; k < H; k++) {
          const zz = sig(z[k] + hu[k]);
          const r = sig(z[H + k] + hu[H + k]);
          const n = Math.tanh(z[2 * H + k] + r * (hu[2 * H + k] + bhn[k]));
          hn[k] = (1 - zz) * n + zz * h[k];
        }
      }
      h = hn; c = cn;
      for (let k = 0; k < H; k++) sum[k] += h[k];
    }
    const T = X.length || 1;
    const logits = new Float64Array(C);
    let mx = -Infinity;
    for (let j = 0; j < C; j++) {
      let s = bo[j];
      for (let k = 0; k < H; k++) s += h[k] * Wo[k * C + j] + (sum[k] / T) * Wo[(H + k) * C + j];
      logits[j] = s / temperature;
      mx = Math.max(mx, logits[j]);
    }
    let tot = 0;
    for (let j = 0; j < C; j++) { logits[j] = Math.exp(logits[j] - mx); tot += logits[j]; }
    for (let j = 0; j < C; j++) logits[j] /= tot;
    return logits;
  }

  /** The server's max-probability decision rule (recognized / uncertain / unknown) and top-k. */
  decide(p: Float64Array, k = 5) {
    const { tau, margin, classes } = this.header;
    const known = classes.map((c, i) => ({ c, i })).filter(({ c }) => c.sign_id !== '__other__');
    const order = known.sort((a, b2) => p[b2.i] - p[a.i]);
    const p1 = p[order[0].i];
    const p2 = order.length > 1 ? p[order[1].i] : 0;
    const otherIdx = classes.findIndex((c) => c.sign_id === '__other__');
    const argmax = p.indexOf(Math.max(...p));
    const det = this.header.open_set_detector;
    let state: string;
    if (otherIdx >= 0 && argmax === otherIdx) state = 'unknown';
    else if (det) {
      const sc = detectorScore(det, p, known.map(({ i }) => i), otherIdx);
      state = sc >= det.t_recognized ? 'recognized' : sc >= det.t_uncertain ? 'uncertain' : 'unknown';
    } else state = p1 >= tau && p1 - p2 >= margin ? 'recognized' : p1 >= 0.6 * tau ? 'uncertain' : 'unknown';
    return { state, top: order.slice(0, k).map(({ c, i }) => ({ sign_id: c.sign_id, label: c.label, probability: p[i] })) };
  }
}

let cached: Promise<WebModel> | null = null;

/** Download (or reuse) the on-device model. The service worker keeps both files for offline use. */
export function loadWebModel(): Promise<WebModel> {
  cached ??= (async () => {
    const hr = await fetch('/model-web/model.json');
    if (!hr.ok) throw new Error('no on-device model is available from this server');
    const header = (await hr.json()) as WebHeader;
    const wr = await fetch('/model-web/weights.bin');
    if (!wr.ok) throw new Error('on-device model weights unavailable');
    return WebModel.fromBuffers(header, await wr.arrayBuffer());
  })().catch((e) => { cached = null; throw e; });
  return cached;
}

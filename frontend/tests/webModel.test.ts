import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { WebModel } from '../src/lib/webModel.ts';

const fx = JSON.parse(fs.readFileSync(path.join(import.meta.dirname, 'fixtures', 'web_model_parity.json'), 'utf8'));

for (const cs of fx.cases) {
  test(`${cs.kind}: in-browser probabilities match the Python model`, () => {
    const classes = Array.from({ length: cs.C }, (_, i) => ({ index: i, sign_id: `ISL${i}`, label: `S${i}` }));
    const m = WebModel.fromArrays({ format: fx.format, model_id: 't', kind: cs.kind, D: cs.D, C: cs.C, H: cs.H, temperature: cs.temperature,
      tau: 0.5, margin: 0.1, contract: 'x', classes, synthetic: true }, { ...cs.params, norm_mean: cs.norm_mean, norm_std: cs.norm_std });
    cs.X.forEach((X: number[][], n: number) => {
      const p = m.predictProba(X);
      cs.P[n].forEach((q: number, j: number) => assert.ok(Math.abs(p[j] - q) < 2e-5, `${cs.kind} sample ${n} class ${j}: ${p[j]} vs ${q}`));
    });
  });
}

test('decision rule mirrors the server (other class -> unknown; tau and margin)', () => {
  const classes = [{ index: 0, sign_id: 'A', label: 'A' }, { index: 1, sign_id: 'B', label: 'B' }, { index: 2, sign_id: '__other__', label: 'Other' }];
  const m = WebModel.fromArrays({ format: 'isl-nova-web-1', model_id: 't', kind: 'lstm', D: 1, C: 3, H: 1, temperature: 1, tau: 0.6, margin: 0.1,
    contract: 'x', classes, synthetic: true }, {});
  assert.equal(m.decide(Float64Array.from([0.8, 0.1, 0.1])).state, 'recognized');
  assert.equal(m.decide(Float64Array.from([0.45, 0.4, 0.15])).state, 'uncertain');
  assert.equal(m.decide(Float64Array.from([0.2, 0.1, 0.7])).state, 'unknown');
  assert.deepEqual(m.decide(Float64Array.from([0.2, 0.1, 0.7])).top.map((t) => t.sign_id), ['A', 'B']);
});

test('unknown-sign detector score matches Python (isl_nova_ml.openset.detector_score)', async () => {
  const { detectorScore } = await import('../src/lib/webModel.ts');
  const det = { features: ['maxprob', 'margin', 'entropy', 'other'], mu: [0.5, 0.3, -1.0, -0.1], sd: [0.2, 0.15, 0.8, 0.1],
    coef: [1.2, 0.7, 0.9, 1.5], intercept: -0.3, t_recognized: 0.4, t_uncertain: -0.5 };
  const s = detectorScore(det, Float64Array.from([0.55, 0.2, 0.05, 0.2]), [0, 1, 2], 3);
  assert.ok(Math.abs(s - -1.0163115650664611) < 1e-9, String(s));
});

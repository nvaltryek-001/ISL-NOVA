import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { CONTRACT, DIM, SEQ, extractFeatures, windowQuality } from '../src/lib/features.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const fx = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'feature_parity.json'), 'utf8'));

test('fixture targets the same contract', () => {
  assert.equal(fx.contract, CONTRACT);
  assert.equal(fx.feature_dim, DIM);
});

for (const c of fx.cases) {
  test(`TypeScript features match Python reference: ${c.name}`, () => {
    const r = extractFeatures(c.frames, c.aspect);
    assert.equal(r.status, c.status);
    assert.equal(r.features.length, SEQ);
    let worst = 0;
    for (let t = 0; t < SEQ; t++) {
      assert.equal(r.features[t].length, DIM);
      for (let k = 0; k < DIM; k++) worst = Math.max(worst, Math.abs(r.features[t][k] - c.features[t][k]));
    }
    assert.ok(worst < 2e-5, `max abs diff ${worst}`);
  });
}

test('empty and hand-less input is insufficient', () => {
  assert.equal(extractFeatures([]).status, 'insufficient_input');
  const blank = Array.from({ length: 20 }, () => ({ left: null, right: null, pose: null }));
  const r = extractFeatures(blank);
  assert.equal(r.status, 'insufficient_input');
  assert.equal(r.handRatio, 0);
  assert.equal(windowQuality(blank).hands, 0);
});

test('contract 2.0.0 face block matches Python', async () => {
  const { extractFeaturesFor, CONTRACT_V2, FACE_DIM } = await import('../src/lib/features.ts');
  const fx2 = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'feature_parity_v2.json'), 'utf8'));
  assert.equal(fx2.contract, CONTRACT_V2);
  assert.equal(fx2.face_dim, FACE_DIM);
  for (const c of fx2.cases) {
    const r = extractFeaturesFor(CONTRACT_V2, c.frames, c.aspect);
    assert.equal(r.features[0].length, DIM + FACE_DIM);
    c.face_features.forEach((row: number[], t: number) => row.forEach((v, j) => {
      assert.ok(Math.abs(r.features[t][DIM + j] - v) < 2e-5, `${c.name} t=${t} j=${j}: ${r.features[t][DIM + j]} vs ${v}`);
    }));
  }
});

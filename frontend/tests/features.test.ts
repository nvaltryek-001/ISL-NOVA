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

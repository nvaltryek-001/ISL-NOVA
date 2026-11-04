// Runs only when E2E_MODEL_TAG names a published model release (set in CI).
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, describe, test } from 'node:test';
import { launch, newPage, repo, startServer } from './harness.mjs';

const TAG = process.env.E2E_MODEL_TAG;
let srv, browser, sample;

describe('trained INCLUDE model', { skip: !TAG && 'E2E_MODEL_TAG not set' }, () => {
  before(async () => {
    srv = await startServer({ withModel: true });
    browser = await launch();
    sample = fs.mkdtempSync(path.join(os.tmpdir(), 'isl-sample-'));
    const tgz = path.join(sample, 's.tgz');
    execFileSync('curl', ['-fsSL', '-o', tgz, `https://github.com/nvaltryek-001/ISL-NOVA/releases/download/${TAG}/include_test_landmark_sample.tar.gz`]);
    execFileSync('tar', ['-xzf', tgz, '-C', sample]);
  });
  after(async () => { await browser?.close(); srv?.stop(); });

  test('UI reports the live model and its held-out metrics', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/');
    await page.getByText(/Model live · 200 signs/).waitFor();
    assert.equal(await page.getByText('No trained recognition model is active').count(), 0);
    await page.goto('/ai');
    await page.getByText('Held-out test metrics').waitFor();
    await page.getByText(/^Top-1$/).waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('held-out INCLUDE test landmarks are recognised through the API', async () => {
    const man = JSON.parse(fs.readFileSync(path.join(sample, 'manifest.json'), 'utf8'));
    const py = `import json,sys; sys.path.insert(0, "ml"); from isl_nova_ml.data import load_landmarks
f,a = load_landmarks(sys.argv[1]); print(json.dumps({"frames": f, "aspect": a}))`;
    let correct = 0;
    for (const e of man.entries) {
      const body = execFileSync(process.env.PYTHON || 'python3', ['-c', py, path.join(sample, e.landmarks_path)], { cwd: repo, maxBuffer: 1 << 26 }).toString();
      const r = await (await fetch(`${srv.base}/api/v1/predict/sequence`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })).json();
      assert.ok(['recognized', 'uncertain', 'unknown'].includes(r.state), r.state);
      assert.equal(r.synthetic, false);
      if (r.top[0]?.sign_id === e.sign_id) correct++;
    }
    console.log(`sample top-1: ${correct}/${man.entries.length}`);
    assert.ok(correct >= man.entries.length * 0.75, `only ${correct}/${man.entries.length} correct`);
  });

  test('live studio with a real model: camera runs and capture is offered', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/live');
    assert.equal(await page.getByText('Model unavailable: no predictions will be shown').count(), 0);
    await page.getByRole('button', { name: 'Start camera' }).click();
    await page.getByText('LIVE', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });
});

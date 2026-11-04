// Post-deployment smoke test against a running ISL NOVA URL.
// usage: node tests/deploy/smoke.mjs <base-url> <landmark-sample-dir> <report.json>
// Read-only: no accounts are created and nothing is written to the deployment.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium } from 'playwright';

const [base, sampleDir, out] = process.argv.slice(2);
const rep = { base, checks: [] };
const check = (name, ok, detail) => { rep.checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail ?? ''}`); };
const getJson = async (p) => { const r = await fetch(base + p); return [r, await r.json()]; };

let [r, j] = await getJson('/api/v1/health');
for (let i = 0; i < 10 && !r.ok; i++) { await new Promise((s) => setTimeout(s, 10000)); [r, j] = await getJson('/api/v1/health'); } // free plan cold start
check('health', r.ok && j.status === 'ok', JSON.stringify(j.model));
check('security headers', r.headers.get('content-security-policy')?.includes("frame-ancestors 'none'") && r.headers.get('strict-transport-security'),
  r.headers.get('strict-transport-security'));
[r, j] = await getJson('/api/v1/model/info');
rep.model = { model_id: j.model_id, kind: j.kind, synthetic: j.synthetic, n_classes: j.n_classes };
check('model installed', j.available && !j.synthetic && j.n_classes === 200, j.model_id);

const man = JSON.parse(fs.readFileSync(path.join(sampleDir, 'manifest.json'), 'utf8'));
const py = 'import json,sys; sys.path.insert(0, "../ml"); from isl_nova_ml.data import load_landmarks\nf,a = load_landmarks(sys.argv[1]); print(json.dumps({"frames": f, "aspect": a}))';
let correct = 0; const lat = []; const states = {};
for (const e of man.entries) {
  const body = execFileSync(process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), ['-c', py, path.join(sampleDir, e.landmarks_path)], { maxBuffer: 1 << 26 }).toString();
  const t0 = performance.now();
  const res = await (await fetch(`${base}/api/v1/predict/sequence`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })).json();
  lat.push(performance.now() - t0);
  states[res.state] = (states[res.state] || 0) + 1;
  if (res.top?.[0]?.sign_id === e.sign_id) correct++;
}
lat.sort((a, b) => a - b);
rep.predictions = { sequences: man.entries.length, top1_correct: correct, states, round_trip_ms_median: Math.round(lat[lat.length >> 1]) };
check('held-out landmark sample via production API', correct >= man.entries.length * 0.75, `${correct}/${man.entries.length}`);

const browser = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] });
for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  const ctx = await browser.newContext({ viewport, permissions: ['camera'] });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(base + '/');
  await page.getByText(/Model live · 200 signs/).first().waitFor({ state: 'attached', timeout: 60000 });
  await page.goto(base + '/live');
  await page.getByRole('button', { name: /Start camera/ }).click();
  let fps = null;
  try { fps = await page.getByText(/fps · (GPU|CPU)/).first().textContent({ timeout: 90000 }); } catch { /* reported below */ }
  check(`UI + camera pipeline @${viewport.width}px`, fps && errors.length === 0, fps ?? (errors.join('; ') || 'no fps badge'));
  await ctx.close();
}
await browser.close();
rep.passed = rep.checks.every((c) => c.ok);
fs.writeFileSync(out, JSON.stringify(rep, null, 2));
process.exit(rep.passed ? 0 : 1);

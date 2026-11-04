// Diagnose in-browser MediaPipe loading in headless Chromium (CI).
// usage: node tests/live-eval/mediapipe_check.mjs <base-url> <report.json> [chromium flags...]
import fs from 'node:fs';
import { chromium } from 'playwright';

const [base, out, ...flags] = process.argv.slice(2);
const rep = { flags, console: [], failed: [], steps: {} };
const browser = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', ...flags] });
const ctx = await browser.newContext({ permissions: ['camera'] });
const page = await ctx.newPage();
page.on('console', (m) => rep.console.push(`${m.type()}: ${m.text()}`.slice(0, 300)));
page.on('pageerror', (e) => rep.console.push(`pageerror: ${e}`.slice(0, 300)));
page.on('requestfailed', (r) => rep.failed.push(`${r.url()} ${r.failure()?.errorText}`));

// 1. step by step inside the app origin (same CSP as production)
await page.goto(base + '/live');
rep.steps.direct = await page.evaluate(async () => {
  const CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const r = {};
  const t = (p, ms) => Promise.race([p, new Promise((_, j) => setTimeout(() => j(new Error(`timeout ${ms} ms`)), ms))]);
  const t0 = performance.now();
  try {
    const vision = await t(import(CDN + '/vision_bundle.mjs'), 30000); r.import = `ok ${Math.round(performance.now() - t0)} ms`;
    const files = await t(vision.FilesetResolver.forVisionTasks(CDN + '/wasm'), 30000); r.fileset = 'ok';
    r.webgl2 = !!document.createElement('canvas').getContext('webgl2');
    for (const delegate of ['CPU', 'GPU']) {
      const t1 = performance.now();
      try {
        const h = await t(vision.HandLandmarker.createFromOptions(files, { runningMode: 'VIDEO', numHands: 2,
          baseOptions: { modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', delegate } }), 60000);
        r[`hand_${delegate}`] = `ok ${Math.round(performance.now() - t1)} ms`;
        h.close();
      } catch (e) { r[`hand_${delegate}`] = `error ${e?.message ?? e}`.slice(0, 300); }
    }
  } catch (e) { r.error = String(e?.message ?? e).slice(0, 300); }
  return r;
});

// 2. the real UI path
await page.goto(base + '/live');
await page.getByRole('button', { name: /Start camera/ }).click();
const t0 = Date.now();
let ui = 'timeout';
while (Date.now() - t0 < 120000) {
  if (await page.getByText(/fps · (GPU|CPU)/).count()) { ui = await page.getByText(/fps · (GPU|CPU)/).first().textContent(); break; }
  if (await page.getByText('Landmark extractor unavailable.').count()) { ui = 'unavailable: ' + (await page.locator('text=MediaPipe could not be loaded').first().textContent()); break; }
  await page.waitForTimeout(1000);
}
rep.steps.ui = { result: ui, seconds: Math.round((Date.now() - t0) / 1000) };
await browser.close();
fs.writeFileSync(out, JSON.stringify(rep, null, 2));
console.log(JSON.stringify(rep, null, 2));

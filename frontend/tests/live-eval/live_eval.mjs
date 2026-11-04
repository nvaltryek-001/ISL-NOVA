// Live-pipeline evaluation with a VIRTUAL CAMERA.
//
//   node tests/live-eval/live_eval.mjs <base-url> <videos-dir> <out.json>
//
// Each held-out INCLUDE test video (Y4M) is fed to Chromium as its camera
// (--use-file-for-fake-video-capture). The real Live Recognition page then
// runs in-browser MediaPipe, the capture flow, POST /predict/sequence and the
// trained model. This measures the browser pipeline on held-out recordings;
// it is NOT a test with a live person in front of a webcam.
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const [base, dir, outFile] = process.argv.slice(2);
const { model_id, videos } = JSON.parse(fs.readFileSync(path.join(dir, 'videos.json'), 'utf8'));
const results = [];

for (const v of videos) {
  const browser = await chromium.launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${path.join(dir, v.y4m)}`],
  });
  const r = { id: v.id, sign_id: v.sign_id, gloss: v.gloss, duration_s: v.duration_s, offline: v.offline };
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 860 } })).newPage();
    await page.goto(`${base}/live`);
    await page.getByRole('button', { name: 'Start camera' }).click();
    // in-browser MediaPipe is ready when the fps badge appears
    await page.getByText(/fps · (GPU|CPU)/).waitFor({ timeout: 120000 });
    r.delegate = (await page.getByText(/fps · (GPU|CPU)/).innerText()).split('· ')[1];
    // restart the camera so the clip plays from its first frame, then capture immediately
    await page.getByRole('button', { name: 'Stop camera' }).click();
    await page.getByRole('button', { name: 'Start camera' }).click();
    await page.getByText(/fps · (GPU|CPU)/).waitFor({ timeout: 30000 });
    await page.getByLabel('3-second countdown').uncheck();
    const secs = [1.5, 2.5, 3.5].find((s) => s >= v.duration_s) ?? 3.5;
    await page.getByLabel('Capture length').selectOption(String(secs));
    const resp = page.waitForResponse((x) => x.url().endsWith('/api/v1/predict/sequence'), { timeout: 60000 });
    await page.getByRole('button', { name: 'Capture sign now' }).click();
    const body = await (await resp).json();
    r.capture_s = secs;
    r.browser = { state: body.state, top1: body.top?.[0]?.sign_id ?? null, p: body.top?.[0]?.probability ?? null,
      top5: (body.top ?? []).map((t) => t.sign_id), quality: body.quality ?? null, model_id: body.model_id };
  } catch (e) {
    r.error = String(e.message ?? e).slice(0, 300);
  } finally {
    await browser.close();
  }
  results.push(r);
  console.log(`${r.gloss}: browser=${r.browser?.top1 ?? r.error} (${r.browser?.state ?? '-'}) offline=${v.offline.top1} truth=${v.sign_id}`);
}

const ok = results.filter((r) => r.browser);
const acc = (f) => (ok.length ? ok.filter(f).length / ok.length : null);
const summary = {
  model_id, method: 'virtual camera replay of held-out INCLUDE test videos through the Live Recognition page (not a live person)',
  videos: results.length, completed: ok.length, errors: results.length - ok.length,
  browser_top1: acc((r) => r.browser.top1 === r.sign_id),
  browser_top5: acc((r) => r.browser.top5.includes(r.sign_id)),
  browser_recognized_rate: acc((r) => r.browser.state === 'recognized'),
  browser_insufficient_input_rate: acc((r) => r.browser.state === 'insufficient_input'),
  offline_python_top1_same_videos: acc((r) => r.offline.top1 === r.sign_id),
  agreement_browser_vs_offline: acc((r) => r.browser.top1 === r.offline.top1),
  states: ok.reduce((m, r) => ({ ...m, [r.browser.state]: (m[r.browser.state] ?? 0) + 1 }), {}),
};
fs.writeFileSync(outFile, JSON.stringify({ summary, results }, null, 2));
console.log(JSON.stringify(summary, null, 2));

// Regenerates the README screenshots with the published trained model active (E2E_MODEL_TAG).
// Run after `npm run build`:  E2E_MODEL_TAG=model-... node tests/e2e/readme_shots.mjs
import { launch, login, newPage, shotsDir, startServer } from './harness.mjs';
const srv = await startServer({ withModel: true });
const browser = await launch();
const wait = (p) => p.waitForTimeout(2600);
try {
  const { page, ctx } = await newPage(browser, srv.base);
  await login(page);
  const go = async (route, name, extra) => { await page.goto(route); await wait(page); if (extra) await extra(); await page.screenshot({ path: `${shotsDir}/${name}.png` }); };
  await go('/', 'dashboard-model');
  await go('/signs', 'sign-explorer');
  await go('/signs/ISL012', 'sign-detail');
  await go('/academy', 'academy');
  await go('/research', 'research');
  await go('/ai', 'ai-laboratory-model');
  await go('/ai', 'evaluation', async () => { await page.getByRole('tab', { name: 'Evaluation' }).click(); await wait(page); });
  await go('/ai', 'ai-laboratory-new-signers', async () => { await page.getByRole('tab', { name: 'New signers' }).click(); await wait(page); });
  await go('/dataset', 'dataset-lab');
  await go('/communicate', 'communication', async () => {
    for (const w of ['hello', 'friend']) { await page.getByPlaceholder(/Type a meaning/).fill(w); await page.getByRole('button', { name: new RegExp(w, 'i') }).first().click(); }
  });
  await go('/live', 'live-recognition'); // camera left off: MediaPipe loads from a CDN that offline build machines cannot reach
  await go('/kiosk', 'kiosk');
  await page.evaluate(() => localStorage.setItem('isl-nova-prefs', JSON.stringify({ theme: 'dark' })));
  await go('/', 'dashboard-dark');
  await ctx.close();
  const m = await newPage(browser, srv.base, { viewport: { width: 390, height: 844 } });
  await login(m.page);
  await m.page.goto('/'); await wait(m.page); await m.page.screenshot({ path: `${shotsDir}/mobile-dashboard.png` });
  await m.page.goto('/dataset'); await wait(m.page); await m.page.screenshot({ path: `${shotsDir}/mobile-dataset.png` });
  await m.ctx.close();
  const l = await newPage(browser, srv.base);
  await l.page.goto('/login'); await wait(l.page); await l.page.screenshot({ path: `${shotsDir}/login.png` });
  await l.ctx.close();
} finally { await browser.close(); srv.stop(); }
console.log('README screenshots written to', shotsDir);

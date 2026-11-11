// Dev helper: screenshot every route (desktop + mobile, light theme) into $SHOTS (default /tmp/shots).
import fs from 'node:fs';
import { launch, login, newPage, startServer } from './harness.mjs';
const out = process.env.SHOTS || '/tmp/shots';
fs.mkdirSync(out, { recursive: true });
const routes = ['/', '/live', '/analysis', '/signs', '/signs/ISL001', '/communicate', '/academy', '/practice', '/text-to-sign',
  '/conversation', '/classes', '/analytics', '/dataset', '/ai', '/research', '/viz', '/admin', '/settings', '/login', '/kiosk'];
const srv = await startServer({ withModel: true });
const browser = await launch();
try {
  for (const [tag, viewport] of (process.env.NOMOBILE ? [['d', { width: 1440, height: 900 }]] : [['d', { width: 1440, height: 900 }], ['m', { width: 390, height: 844 }]])) {
    const { page, errors } = await newPage(browser, srv.base, { viewport });
    await login(page);
    if (process.env.THEME) { await page.evaluate((th) => localStorage.setItem('isl-nova-prefs', JSON.stringify({ theme: th })), process.env.THEME); }
    for (const r of (process.env.ROUTES ? process.env.ROUTES.split(',') : routes)) {
      await page.goto(r); await page.waitForTimeout(Number(process.env.WAIT || 2600));
      await page.screenshot({ path: `${out}/${tag}${r.replace(/\//g, '_') || '_'}.png`, fullPage: tag === 'd' && !process.env.NOFULL });
    }
    if (errors.length) console.log(tag, 'page errors:', errors.slice(0, 5));
  }
} finally { await browser.close(); srv.stop(); }
console.log('shots in', out);

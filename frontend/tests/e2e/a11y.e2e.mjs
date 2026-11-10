// Automated WCAG scan with axe-core on every main route, light and dark theme.
// Fails on "serious" or "critical" violations. Needs the axe-core dev dependency
// (installed by `npm install`); skipped with a notice if it is missing, unless
// AXE_REQUIRED=1 (set in CI) makes a missing axe-core an error.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { after, before, describe, test } from 'node:test';
import { launch, login, startServer } from './harness.mjs';

const require = createRequire(import.meta.url);
let axeSource = null;
try { axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch { /* not installed */ }
if (!axeSource && process.env.AXE_REQUIRED === '1') throw new Error('axe-core is not installed (npm install)');

const ROUTES = ['/', '/signs', '/signs/ISL012', '/live', '/communicate', '/academy', '/dataset', '/ai', '/research', '/admin',
  '/settings', '/analysis', '/practice', '/text-to-sign', '/conversation', '/classes', '/analytics', '/login', '/register', '/reset-password'];

let srv, browser;
before(async () => { if (!axeSource) return; srv = await startServer(); browser = await launch(); });
after(async () => { await browser?.close(); srv?.stop(); });

describe('axe-core WCAG 2.1 AA scan', { skip: axeSource ? false : 'axe-core not installed' }, () => {
  for (const theme of ['light', 'dark']) {
    test(`no serious or critical violations (${theme} theme)`, { timeout: 240000 }, async () => {
      // bypassCSP only lets the test inject axe; the app's own CSP is unchanged
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, baseURL: srv.base, bypassCSP: true });
      const page = await ctx.newPage();
      await page.addInitScript((t) => localStorage.setItem('isl-nova-prefs', JSON.stringify({ theme: t })), theme);
      await login(page);
      const found = [];
      for (const route of ROUTES) {
        if (route === '/login' || route === '/register' || route === '/reset-password') {
          await page.evaluate(() => sessionStorage.clear());
        }
        await page.goto(route);
        await page.getByRole('heading', { level: 1 }).or(page.getByRole('heading', { level: 2 })).first().waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.classList.contains('dark')), theme === 'dark');
        await page.waitForTimeout(300);
        await page.addScriptTag({ content: axeSource });
        const res = await page.evaluate(async () => {
          const r = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
          return r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
            .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ') + ' :: ' + (n.failureSummary || '').split('\n')[1]) }));
        });
        for (const v of res) found.push({ route, ...v });
      }
      if (found.length) console.log(JSON.stringify(found, null, 1));
      assert.deepEqual(found, []);
      await ctx.close();
    });
  }
});

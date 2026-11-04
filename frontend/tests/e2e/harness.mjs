// E2E harness: starts a fresh ISL NOVA server (temp SQLite DB, temp storage)
// serving the production frontend build, and drives real Chromium with a fake
// camera device. Requires `npm run build` first and Python deps installed.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
export const repo = path.resolve(here, '..', '..', '..');
export const ADMIN = { email: 'admin@example.org', password: 'admin-password-1' };

const freePort = () => new Promise((res) => { const s = net.createServer(); s.listen(0, () => { const p = s.address().port; s.close(() => res(p)); }); });

export async function startServer({ withModel = false } = {}) {
  if (!fs.existsSync(path.join(repo, 'frontend', 'dist', 'index.html'))) throw new Error('run `npm run build` before e2e');
  const port = await freePort();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'isl-nova-e2e-'));
  const env = {
    ...process.env, PYTHONPATH: `${repo}/backend:${repo}/ml`, DATABASE_URL: `sqlite:///${dir}/db.sqlite`,
    STORAGE_DIR: `${dir}/objects`, MODEL_REGISTRY_DIR: `${dir}/models`, JWT_SECRET: 'e2e-secret-'.padEnd(48, 'x'),
    BOOTSTRAP_ADMIN_EMAIL: ADMIN.email, BOOTSTRAP_ADMIN_PASSWORD: ADMIN.password, PBKDF2_ITERATIONS: '1000',
    CORS_ORIGINS: `http://127.0.0.1:${port}`, AUTH_RATE_LIMIT_PER_MINUTE: '1000', RATE_LIMIT_PER_MINUTE: '10000',
  };
  if (withModel && process.env.E2E_MODEL_TAG) {
    // install the published, trained model exactly as an operator would
    const r = spawnSync(process.env.PYTHON || 'python3', ['scripts/fetch_model.py', '--tag', process.env.E2E_MODEL_TAG, '--registry', `${dir}/models`, '--promote'],
      { cwd: repo, env, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(`fetch_model failed: ${r.stderr}`);
  }
  const proc = spawn(process.env.PYTHON || 'python3', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port), '--log-level', 'warning'],
    { cwd: path.join(repo, 'backend'), env, stdio: ['ignore', 'ignore', 'pipe'] });
  let stderr = '';
  proc.stderr.on('data', (d) => { stderr += d; });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${base}/api/v1/health`)).ok) break; } catch { /* not up yet */ }
    if (proc.exitCode !== null) throw new Error(`server exited: ${stderr}`);
    await new Promise((r) => setTimeout(r, 150));
  }
  return { base, dir, stop: () => { proc.kill('SIGTERM'); fs.rmSync(dir, { recursive: true, force: true }); } };
}

export async function launch({ camera = 'allow' } = {}) {
  const args = ['--use-fake-device-for-media-stream'];
  if (camera === 'allow') args.push('--use-fake-ui-for-media-stream');
  return chromium.launch({ args });
}

export async function newPage(browser, base, { viewport = { width: 1440, height: 900 }, permissions } = {}) {
  const ctx = await browser.newContext({ viewport, baseURL: base, permissions });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    // network failures to the MediaPipe CDN are expected in offline sandboxes
    if (m.type() === 'error' && !/cdn\.jsdelivr|storage\.googleapis|Failed to load resource/.test(m.text())) errors.push(m.text());
  });
  return { page, ctx, errors };
}

export async function login(page, { email, password } = ADMIN) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
}

export async function apiAs(base, creds) {
  const r = await fetch(`${base}/api/v1/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(creds) });
  const { access_token } = await r.json();
  return async (pathname, opts = {}) => {
    const res = await fetch(`${base}/api/v1${pathname}`, { ...opts, headers: { Authorization: `Bearer ${access_token}`, 'Content-Type': 'application/json', ...(opts.headers || {}) } });
    return { status: res.status, body: await res.json().catch(() => null) };
  };
}

export async function makeUser(base, admin, email, roles) {
  await fetch(`${base}/api/v1/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: 'password-123!', display_name: email.split('@')[0] }) });
  const users = (await admin('/admin/users')).body;
  const u = users.find((x) => x.email === email);
  if (roles) await admin(`/admin/users/${u.id}`, { method: 'PATCH', body: JSON.stringify({ roles }) });
  return { email, password: 'password-123!' };
}

export const shotsDir = path.join(repo, 'docs', 'screenshots');

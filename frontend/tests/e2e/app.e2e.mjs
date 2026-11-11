import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import { after, before, describe, test } from 'node:test';
import { ADMIN, apiAs, launch, login, makeUser, newPage, shotsDir, startServer } from './harness.mjs';

const SHOTS = process.env.E2E_SCREENSHOTS === '1';
let srv, browser, admin;

before(async () => {
  srv = await startServer();
  browser = await launch();
  admin = await apiAs(srv.base, ADMIN);
  if (SHOTS) fs.mkdirSync(shotsDir, { recursive: true });
});
after(async () => { await browser?.close(); srv?.stop(); });

// RFC 6238 TOTP for the two-factor E2E (SHA-1, 6 digits, 30 s)
function totpCode(secret, offset = 0) {
  const alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of secret.replace(/=+$/, '')) bits += alpha.indexOf(ch).toString(2).padStart(5, '0');
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30) + offset));
  const mac = crypto.createHmac('sha1', key).update(buf).digest();
  const o = mac[mac.length - 1] & 15;
  return String((mac.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, '0');
}

const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${shotsDir}/${name}.png` }); };

// README screenshots are captured FIRST, on the untouched seeded state, so they
// show the project's real status (200 unverified slots, no model, no data).
describe('screenshots (E2E_SCREENSHOTS=1)', { skip: !SHOTS }, () => {
  test('capture product screenshots', async () => {
    const { page, ctx } = await newPage(browser, srv.base);
    await login(page);
    const go = async (route, ready, name, extra) => {
      await page.goto(route);
      await page.getByText(ready).first().waitFor();
      if (extra) await extra();
      await page.waitForTimeout(600);
      await shot(page, name);
    };
    await go('/', 'Vocabulary by category', 'dashboard');
    await go('/signs', 'ISL001', 'sign-explorer');
    await go('/signs/ISL012', 'Reference sources', 'sign-detail');
    await go('/dataset', 'Readiness funnel', 'dataset-lab');
    await go('/ai', 'No model is serving predictions', 'ai-laboratory', async () => {
      await page.getByRole('tab', { name: 'Feature contract' }).click();
      await page.getByText('Definition').waitFor();
    });
    await go('/communicate', 'Pick signs', 'communication', async () => {
      for (const w of ['hello', 'friend']) {
        await page.getByPlaceholder(/Type a meaning/).fill(w);
        await page.getByRole('button', { name: new RegExp(w, 'i') }).first().click();
      }
    });
    await go('/live', 'Model unavailable: no predictions', 'live-recognition', async () => {
      await page.getByRole('button', { name: 'Start camera' }).click();
      await page.getByText('LIVE', { exact: true }).waitFor();
      await page.waitForTimeout(1500);
    });
    await go('/kiosk', 'Quick phrases', 'kiosk');
    await ctx.close();
    const m = await newPage(browser, srv.base, { viewport: { width: 390, height: 844 } });
    await m.page.goto('/');
    await m.page.getByText('Signs in the vocabulary').waitFor();
    await m.page.waitForTimeout(600);
    await m.page.screenshot({ path: `${shotsDir}/mobile-dashboard.png` });
    await m.ctx.close();
    const d = await newPage(browser, srv.base);
    await d.page.goto('/');
    await d.page.evaluate(() => localStorage.setItem('isl-nova-prefs', JSON.stringify({ theme: 'dark' })));
    await d.page.reload();
    await d.page.getByText('Vocabulary by category').waitFor();
    await d.page.waitForTimeout(600);
    await d.page.screenshot({ path: `${shotsDir}/dashboard-dark.png` });
    await d.ctx.close();
  });
});

describe('startup and truthful empty state', () => {
  test('dashboard shows real zero counts and model unavailable', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/');
    await page.getByText('No trained recognition model is active').waitFor();
    // counts animate up to their real values; data-value carries the final number
    await page.locator('.card', { hasText: 'Signs in the vocabulary' }).locator('[data-value="200"]').waitFor();
    assert.equal(await page.getByText('Workspace', { exact: true }).count(), 0); // staff-only section hidden from visitors
    assert.equal(await page.getByRole('heading', { level: 1 }).count(), 1);
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('unknown route renders 404 and API 404 is JSON', async () => {
    const { page, ctx } = await newPage(browser, srv.base);
    await page.goto('/does-not-exist');
    await page.getByText('This page does not exist.').waitFor();
    const r = await fetch(`${srv.base}/api/v1/nope`);
    assert.equal(r.status, 404);
    assert.equal((await r.json()).error.code, 'not_found');
    await ctx.close();
  });
});

describe('authentication and RBAC', () => {
  test('register as learner; admin area is hidden and refused', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/register');
    await page.getByRole('button', { name: 'Create account' }).click();
    await page.getByText('Enter a valid email address').waitFor();
    await page.getByLabel('Name').fill('Learner One');
    await page.getByLabel('Email').fill('learner1@example.org');
    await page.getByLabel('Password').fill('long-password-1');
    await page.getByRole('button', { name: 'Create account' }).click();
    await page.waitForURL(`${srv.base}/`);
    await page.getByText('Welcome, Learner One').waitFor();
    assert.equal(await page.getByRole('link', { name: 'Administration' }).count(), 0);
    await page.goto('/admin');
    await page.getByText("You don't have access to this area").waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('wrong password shows an error', async () => {
    const { page, ctx } = await newPage(browser, srv.base);
    await page.goto('/login');
    await page.getByLabel('Email').fill(ADMIN.email);
    await page.getByLabel('Password').fill('wrong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByText('email or password is incorrect').waitFor();
    await ctx.close();
  });
  test('teacher class: create, learner joins with the code, teacher dashboard; analytics; review queue', async () => {
    const teacher = await makeUser(srv.base, admin, 'teacher1@example.org', ['teacher']);
    const learner = await makeUser(srv.base, admin, 'pupil1@example.org');
    const tp = await newPage(browser, srv.base);
    await login(tp.page, teacher);
    await tp.page.goto('/classes');
    await tp.page.getByLabel('New class name').fill('Class 7B');
    await tp.page.getByRole('button', { name: 'Create class' }).click();
    const code = (await tp.page.getByTestId('class-code').first().textContent()).trim();
    assert.equal(code.length, 8);

    const lp = await newPage(browser, srv.base);
    await login(lp.page, learner);
    const me = await apiAs(srv.base, learner);
    for (const ok of [true, false, false]) await me('/learning/attempts', { method: 'POST', body: JSON.stringify({ sign_id: 'ISL004', mode: 'quiz', correct: ok }) });
    await lp.page.goto('/classes');
    await lp.page.getByLabel('Class code').fill(code);
    await lp.page.getByRole('button', { name: 'Join', exact: true }).click();
    await lp.page.getByText('Class 7B').waitFor();
    await lp.page.goto('/academy');
    await lp.page.getByRole('tab', { name: 'My progress' }).click();
    await lp.page.getByText('Due for review today').waitFor();
    await lp.page.getByRole('link', { name: 'Practise' }).first().waitFor();

    await tp.page.reload();
    await tp.page.getByRole('button', { name: 'Open' }).click();
    await tp.page.getByText('pupil1').first().waitFor();
    await tp.page.getByRole('cell', { name: '33%' }).waitFor();

    await tp.page.goto('/analytics');
    await tp.page.getByText("You don't have access to this area").waitFor();
    const ap = await newPage(browser, srv.base);
    await login(ap.page);
    await ap.page.goto('/analytics');
    await ap.page.getByText('Activity per day').waitFor();
    await ap.page.getByText('Most practised signs').waitFor();
    assert.deepEqual([...tp.errors, ...lp.errors, ...ap.errors], []);
    for (const x of [tp, lp, ap]) await x.ctx.close();
  });

  test('learning progress shows streak, points and earned badges from real attempts', async () => {
    const creds = await makeUser(srv.base, admin, 'streak1@example.org');
    const me = await apiAs(srv.base, creds);
    for (const sid of ['ISL001', 'ISL002', 'ISL003']) {
      assert.equal((await me('/learning/attempts', { method: 'POST', body: JSON.stringify({ sign_id: sid, mode: 'quiz', correct: true }) })).status, 201);
    }
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page, creds);
    await page.goto('/academy');
    await page.getByRole('tab', { name: 'My progress' }).click();
    await page.getByText('Streaks and badges').waitFor();
    await page.getByText(/30 points/).waitFor();                     // 3 correct x 10 points
    const first = page.getByRole('listitem').filter({ hasText: 'First step' });
    assert.equal(await first.getByText('Earned', { exact: true }).count(), 1);
    const ten = page.getByRole('listitem').filter({ hasText: 'Ten signs' });
    assert.equal(await ten.getByText('Not earned yet').count(), 1);
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('an expired access token is renewed with the refresh token; sign out revokes it', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    const before = await page.evaluate(() => JSON.parse(sessionStorage.getItem('isl-nova-session')));
    assert.ok(before.refresh);
    await page.evaluate(() => { const s = JSON.parse(sessionStorage.getItem('isl-nova-session')); s.token = 'expired.invalid.token'; sessionStorage.setItem('isl-nova-session', JSON.stringify(s)); });
    await page.goto('/settings');
    await page.getByRole('heading', { name: 'Settings & activity' }).waitFor();
    await page.waitForFunction(() => JSON.parse(sessionStorage.getItem('isl-nova-session') || '{}').token !== 'expired.invalid.token');
    assert.equal(page.url(), `${srv.base}/settings`);   // still signed in, not sent to the login page
    const after = await page.evaluate(() => JSON.parse(sessionStorage.getItem('isl-nova-session')));
    assert.notEqual(after.token, 'expired.invalid.token');
    assert.notEqual(after.refresh, before.refresh);   // rotated
    const old = await fetch(`${srv.base}/api/v1/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: before.refresh }) });
    assert.equal(old.status, 401);
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('two-factor sign-in: set up, sign in with a code, turn off', async () => {
    const creds = await makeUser(srv.base, admin, 'tfa1@example.org');
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page, creds);
    await page.goto('/settings');
    await page.getByRole('button', { name: 'Set up two-factor' }).click();
    const secret = (await page.getByTestId('totp-secret').textContent()).trim();
    await page.getByLabel('Code from the app').fill(totpCode(secret, -1));
    await page.getByRole('button', { name: 'Turn on two-factor' }).click();
    await page.getByText('On. Sign-in asks for a code from your authenticator app.').waitFor();
    await ctx.close();

    const u = await newPage(browser, srv.base);
    await u.page.goto('/login');
    await u.page.getByLabel('Email').fill(creds.email);
    await u.page.getByLabel('Password').fill(creds.password);
    await u.page.getByRole('button', { name: 'Sign in' }).click();
    await u.page.getByLabel('Authenticator code').fill(totpCode(secret));
    await u.page.getByRole('button', { name: 'Sign in' }).click();
    await u.page.waitForURL((x) => !x.pathname.startsWith('/login'));
    await u.page.goto('/settings');
    await u.page.getByLabel('Current code').fill(totpCode(secret, 1));
    await u.page.getByRole('button', { name: 'Turn off two-factor' }).click();
    await u.page.getByText('Off. Add a second step to sign-in with any authenticator app.').waitFor();
    assert.deepEqual(errors.concat(u.errors), []);
    await u.ctx.close();
  });

  test('admin reset code, reset page, sign out everywhere', async () => {
    const creds = await makeUser(srv.base, admin, 'reset1@example.org');
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    await page.goto('/admin');
    await page.getByLabel('Search users').fill('reset1');
    const row = page.getByRole('row').filter({ hasText: creds.email });
    await row.getByRole('button', { name: 'Reset code' }).click();
    const code = (await page.getByTestId('reset-code').textContent()).trim();
    assert.ok(code.length >= 20);
    await ctx.close();

    const u = await newPage(browser, srv.base);
    await u.page.goto('/login');
    await u.page.getByRole('link', { name: 'Have a reset code?' }).click();
    await u.page.getByRole('heading', { name: 'Reset your password' }).waitFor();
    await u.page.getByLabel('Reset code').fill(code);
    await u.page.getByLabel('New password').fill('fresh-password-9');
    await u.page.getByRole('button', { name: 'Set new password' }).click();
    await u.page.getByText('Password changed and all earlier sessions signed out.').waitFor();
    await login(u.page, { email: creds.email, password: 'fresh-password-9' });
    await u.page.goto('/settings');
    u.page.once('dialog', (d) => d.accept());
    await u.page.getByRole('button', { name: 'Sign out everywhere' }).click();
    await u.page.getByRole('button', { name: 'Sign in' }).first().waitFor();
    const r = await fetch(`${srv.base}/api/v1/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: creds.email, password: 'fresh-password-9' }) });
    assert.equal(r.status, 200);
    assert.deepEqual(errors.concat(u.errors), []);
    await u.ctx.close();
  });
});

describe('vocabulary', () => {
  test('search, open detail and bookmark', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    await page.goto('/signs');
    await page.getByPlaceholder('Search by meaning, gloss or ID…').fill('mother');
    await page.getByText('2 signs', { exact: true }).waitFor(); // Mother, Grandmother
    await page.getByRole('link', { name: /^Mother/ }).click();
    await page.getByRole('heading', { name: 'Mother' }).waitFor();
    await page.getByText('Not yet verified by a qualified ISL reviewer').waitFor();
    await page.getByRole('button', { name: 'Bookmark' }).click();
    await page.getByRole('button', { name: 'Bookmarked' }).waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('vocabulary is fixed at 200; edit, retire and restore a sign (CRUD)', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    await page.goto('/signs');
    await page.getByRole('button', { name: 'New sign' }).click();
    const d = page.getByRole('dialog');
    await d.getByLabel('Sign ID').fill('ISL201');
    await d.getByLabel('Canonical name').fill('Water');
    await d.getByLabel('English meaning (draft)').fill('water');
    await d.getByLabel('Hands required').selectOption('one');
    await d.getByRole('button', { name: 'Create sign' }).click();
    await d.getByText('the vocabulary is fixed at 200 signs').waitFor();
    await d.getByRole('button', { name: 'Cancel' }).click();
    await page.goto('/signs/ISL150');
    await page.getByRole('button', { name: 'Edit sign' }).click();
    await page.getByRole('dialog').getByLabel('Annotation notes').fill('Two regional variants observed');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await page.getByText('Two regional variants observed').waitFor();
    await page.getByRole('button', { name: 'Retire' }).click();
    await page.getByText('Retired', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Restore' }).click();
    await page.getByRole('button', { name: 'Retire' }).waitFor();
    const full = await admin('/signs', { method: 'POST', body: JSON.stringify({ sign_id: 'ISL201', canonical_sign_name: 'x', category: 'daily_needs' }) });
    assert.equal(full.status, 409);
    assert.equal(full.body.error.code, 'vocabulary_fixed');
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('linguist verifies a sign through the review workflow', async () => {
    const ling = await makeUser(srv.base, admin, 'linguist@example.org', ['linguist']);
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page, ling);
    await page.goto('/signs/ISL012');
    await page.getByRole('button', { name: '→ review pending' }).click();
    await page.getByRole('dialog').getByLabel('Review note').fill('Compared with INCLUDE reference video');
    await page.getByRole('button', { name: 'Confirm' }).click();
    await page.getByRole('button', { name: '→ verified' }).click();
    await page.getByText('Document the sign first').waitFor();
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
    await page.getByRole('button', { name: 'Edit sign' }).click();
    const ed = page.getByRole('dialog');
    await ed.getByLabel('Hands required').selectOption('one');
    await ed.getByLabel('Movement').selectOption('dynamic');
    await ed.getByLabel('Linguistic description').fill('Flat hand moves outward from the forehead');
    await ed.getByRole('button', { name: 'Save changes' }).click();
    await ed.waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: '→ verified' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByLabel('Review note').fill('Form confirmed by reviewer');
    assert.equal(await dlg.getByRole('button', { name: 'Confirm' }).isDisabled(), true, 'checklist gates verification');
    for (const l of ['I watched the licensed reference', 'Handshape, location, movement', 'The English meaning is an accurate']) await dlg.getByLabel(new RegExp(l)).check();
    await page.getByRole('button', { name: 'Confirm' }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    // once verified, the only forward action offered is "→ review pending"
    await page.getByRole('button', { name: '→ review pending' }).waitFor();
    await page.getByText('Form confirmed by reviewer').waitFor();
    const detail = await (await fetch(`${srv.base}/api/v1/signs/ISL012`)).json();
    assert.equal(detail.verification_status, 'verified');
    const stats = await (await fetch(`${srv.base}/api/v1/dataset/stats`)).json();
    assert.equal(stats.verified_classes, 1);
    assert.deepEqual(errors, []);
    await ctx.close();
  });
});

describe('dataset workflow', () => {
  test('signer, consent, recording studio upload, four-eyes review', { timeout: 180000 }, async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    await page.goto('/dataset');
    await page.getByRole('tab', { name: 'Signers & consent' }).click();
    await page.getByRole('button', { name: 'Register signer' }).click();
    await page.getByRole('dialog').getByLabel('Dominant hand').selectOption('right');
    await page.getByRole('dialog').getByRole('button', { name: 'Register' }).click();
    const consent = page.getByRole('dialog', { name: /Informed consent/ });
    await consent.waitFor();
    assert.equal(await consent.getByRole('button', { name: 'Record consent' }).isDisabled(), true);
    await consent.getByLabel('Use my recordings to train recognition models').check();
    await consent.getByLabel('The signer has explicitly confirmed this consent.').check();
    await consent.getByRole('button', { name: 'Record consent' }).click();
    await page.getByText('model training', { exact: true }).waitFor();

    await page.getByRole('tab', { name: 'Recording Studio' }).click();
    const signer = page.getByLabel('Signer');
    await signer.selectOption({ index: 1 });
    await page.getByRole('button', { name: 'Open session' }).click();
    await page.getByText(/Session SES-/).first().waitFor();
    await page.getByLabel('Search sign to record').fill('hello');
    await page.getByRole('button', { name: /Hello\s*ISL/ }).click();
    await page.getByRole('button', { name: 'Start camera' }).click();
    await page.getByText('LIVE', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Record clip' }).click();
    await page.getByLabel('Recorded clip preview').waitFor({ timeout: 60000 }); // MediaPipe on CPU can slow the page in CI
    await page.getByRole('button', { name: 'Upload for review' }).click();
    await page.getByText(/Uploaded REC-/).waitFor({ timeout: 60000 });

    await page.getByRole('tab', { name: 'Review queue' }).click();
    await page.getByRole('row', { name: /ISL012/ }).getByRole('button', { name: 'Open' }).click();
    await page.getByRole('button', { name: 'Annotate as ISL012' }).click();
    await page.getByRole('row', { name: /ISL012/ }).first().waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();

    // second person approves (four-eyes rule)
    const reviewer = await makeUser(srv.base, admin, 'reviewer@example.org', ['linguist']);
    const r = await newPage(browser, srv.base);
    await login(r.page, reviewer);
    await r.page.goto('/dataset');
    await r.page.getByRole('tab', { name: 'Review queue' }).click();
    await r.page.getByRole('button', { name: 'Approve' }).click();
    await r.page.getByText('Review recorded').waitFor();
    const stats = await (await fetch(`${srv.base}/api/v1/dataset/stats`)).json();
    assert.equal(stats.approved_samples, 1);
    assert.equal(stats.classes_with_recordings, 1);
    assert.equal(stats.classes_approved_for_training, 0, 'one sample is never enough for training');
    assert.deepEqual(r.errors, []);
    await r.ctx.close();
  });
});

describe('recognition', () => {
  test('live studio: camera works, model unavailable is explicit, capture is gated', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/live');
    await page.getByText('Model unavailable: no predictions will be shown').waitFor();
    await page.getByRole('button', { name: 'Start camera' }).click();
    await page.getByText('LIVE', { exact: true }).waitFor();
    await page.waitForTimeout(500);
    // read extractor state and button state in one snapshot (MediaPipe may finish loading between two reads)
    const snap = await page.evaluate(() => ({
      notReady: /Loading hand-tracking models|Landmark extractor unavailable/.test(document.body.innerText),
      disabled: [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Capture sign'))?.disabled,
    }));
    if (snap.notReady) assert.equal(snap.disabled, true, 'capture must be disabled while hand tracking is not ready');
    const r = await (await fetch(`${srv.base}/api/v1/predict/sequence`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ frames: [] }) })).json();
    assert.equal(r.state, 'model_unavailable');
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('camera permission denied is handled', async () => {
    const denied = await launch({ camera: 'deny' });
    const { page, ctx } = await newPage(denied, srv.base, { permissions: [] });
    await page.goto('/live');
    await page.getByRole('button', { name: 'Start camera' }).click();
    await page.getByText(/Camera permission denied|Camera unavailable/).waitFor();
    await ctx.close();
    await denied.close();
  });

  test('kiosk mode shows honest unavailable state and exits', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await page.goto('/kiosk');
    await page.getByRole('button', { name: 'Recognition unavailable' }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Recognition unavailable' }).isDisabled(), true);
    await page.getByRole('button', { name: 'हिन्दी' }).click();
    await page.getByText('No verified quick phrases for हिन्दी yet.').waitFor();
    await page.getByRole('button', { name: 'Exit kiosk' }).click();
    await page.waitForURL(`${srv.base}/`);
    assert.deepEqual(errors, []);
    await ctx.close();
  });
});

describe('modules render with real data', () => {
  test('every main route renders one h1 without errors', async () => {
    const { page, errors, ctx } = await newPage(browser, srv.base);
    await login(page);
    for (const [route, h1] of [['/', /Welcome/], ['/communicate', /Communication/], ['/academy', /Learning Academy/], ['/dataset', /Dataset Lab/], ['/ai', /AI Laboratory/], ['/research', /Research Centre/], ['/viz', /3D Landmark Viewer/], ['/admin', /Administration/], ['/settings', /Settings/], ['/analysis', /Video Analysis/], ['/practice', /Practice Coach/], ['/text-to-sign', /Text to Sign/], ['/conversation', /Conversation/], ['/classes', /Classes/], ['/analytics', /Analytics/]]) {
      await page.goto(route);
      await page.getByRole('heading', { level: 1, name: h1 }).waitFor();
      assert.equal(await page.getByRole('heading', { level: 1 }).count(), 1, route);
      const unnamed = await page.locator('button').evaluateAll((bs) => bs.filter((b) => !b.textContent.trim() && !b.getAttribute('aria-label') && b.offsetParent !== null).length);
      assert.equal(unnamed, 0, `unnamed buttons on ${route}`);
    }
    await page.goto('/ai');
    await page.getByRole('tab', { name: 'Feature contract' }).click();
    await page.getByText('isl-nova-fc-1.0.0').first().waitFor();
    await page.goto('/admin');
    await page.getByRole('tab', { name: 'Audit log' }).click();
    await page.getByText('auth.login').first().waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('communication composer builds editable text', async () => {
    const { page, ctx } = await newPage(browser, srv.base);
    await page.goto('/communicate');
    await page.getByPlaceholder(/Type a meaning/).fill('school');
    await page.getByRole('button', { name: /School/ }).first().click();
    await page.getByPlaceholder(/Type a meaning/).fill('teacher');
    await page.getByRole('button', { name: /Teacher/ }).first().click();
    await page.waitForFunction(() => document.querySelector('textarea')?.value === 'School Teacher');
    await page.getByText(/2 meanings are unverified/).waitFor();
    await ctx.close();
  });

  test('interface switches to Hindi and Kannada and persists; meanings show draft status', async () => {
    const { page, ctx, errors } = await newPage(browser, srv.base);
    await page.goto('/signs');
    await page.getByRole('heading', { level: 1, name: 'Sign Explorer' }).waitFor();
    await page.getByLabel('Interface language').selectOption('hi');
    await page.getByRole('heading', { level: 1, name: 'संकेत खोज' }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.lang), 'hi');
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'लाइव पहचान' }).waitFor();
    await page.getByText('सभी 200 संकेतों को English, हिन्दी या ಕನ್ನಡ में अर्थ से खोजें।').waitFor(); // page description translated
    await page.locator('[title="मसौदा अनुवाद"]').first().waitFor(); // draft meanings stay marked on every card
    await page.reload();
    await page.getByRole('heading', { level: 1, name: 'संकेत खोज' }).waitFor();
    await page.getByLabel('इंटरफ़ेस भाषा').selectOption('kn');
    await page.getByRole('heading', { level: 1, name: 'ಸಂಜ್ಞೆ ಅನ್ವೇಷಕ' }).waitFor();
    const cov = await (await fetch(`${srv.base}/api/v1/translations/coverage`)).json();
    assert.equal(cov.languages.hi.draft, 200); assert.equal(cov.languages.kn.verified, 0);
    await page.getByLabel('ಇಂಟರ್ಫೇಸ್ ಭಾಷೆ').selectOption('en');
    await page.getByRole('heading', { level: 1, name: 'Sign Explorer' }).waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('text to sign matches English and Hindi words and flags unknown words', async () => {
    const { page, ctx, errors } = await newPage(browser, srv.base);
    await page.goto('/text-to-sign');
    await page.getByLabel('Text').fill('good morning teacher zebra');
    await page.getByRole('button', { name: 'Show signs' }).click();
    const matched = page.getByLabel('Matched words');
    await matched.getByRole('button', { name: /good morning ISL010/ }).waitFor();
    await matched.getByRole('button', { name: /teacher ISL150/ }).waitFor();
    await matched.getByText('zebra: no sign in vocabulary').waitFor();
    await page.getByLabel('Text').fill('नमस्ते दोस्त');
    await page.getByRole('button', { name: 'Show signs' }).click();
    await matched.getByRole('button', { name: /नमस्ते ISL012/ }).waitFor();
    await matched.getByRole('button', { name: /दोस्त ISL005/ }).waitFor();
    const refs = await (await fetch(`${srv.base}/api/v1/practice/status`)).json();
    if (refs.available) await page.getByRole('img', { name: /Reference animation/ }).waitFor();
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('practice coach: choose a sign, reference shown, attempt gated on camera', async () => {
    const { page, ctx, errors } = await newPage(browser, srv.base);
    await page.goto('/practice');
    await page.getByRole('heading', { level: 1, name: 'Practice Coach' }).waitFor();
    await page.getByLabel('Search signs').fill('hello');
    await page.getByRole('button', { name: /ISL012/ }).first().click();
    const refs = await (await fetch(`${srv.base}/api/v1/practice/status`)).json();
    if (refs.available) await page.getByRole('img', { name: /Reference animation: Hello/ }).waitFor();
    else await page.getByText('Reference animations are not installed on this server.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Try it (3-2-1)' }).isDisabled(), true, 'disabled until the camera runs');
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('installable PWA: manifest, service worker, offline shell and offline badge', async () => {
    const { page, ctx, errors } = await newPage(browser, srv.base);
    const man = await (await fetch(`${srv.base}/manifest.webmanifest`)).json();
    assert.equal(man.display, 'standalone');
    assert.ok(man.icons.some((i) => i.sizes === '512x512'));
    await page.goto('/');
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.reload();
    await page.getByRole('heading', { level: 1 }).waitFor();
    await ctx.setOffline(true);
    await page.goto('/signs').catch(() => {});
    await page.getByText('Offline', { exact: true }).first().waitFor();
    await ctx.setOffline(false);
    assert.deepEqual(errors.filter((e) => !/Failed to fetch|NetworkError|ERR_INTERNET_DISCONNECTED/.test(e)), []);
    await ctx.close();
  });

  test('light theme is the default and the toggle switches to dark and back', async () => {
    const { page, ctx, errors } = await newPage(browser, srv.base);
    await page.goto('/');
    const isDark = () => page.evaluate(() => document.documentElement.classList.contains('dark'));
    assert.equal(await isDark(), false);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    assert.equal(bg, 'rgb(246, 247, 251)');
    await page.getByRole('button', { name: 'Switch to dark theme' }).click();
    assert.equal(await isDark(), true);
    await page.reload();
    assert.equal(await isDark(), true, 'theme choice persists');
    await page.getByRole('button', { name: 'Switch to light theme' }).click();
    assert.equal(await isDark(), false);
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test('accessibility basics and responsive layout on phone, tablet and desktop', async () => {
    const routes = ['/', '/signs', '/live', '/communicate', '/academy', '/dataset', '/ai', '/research', '/admin', '/settings', '/analysis', '/practice', '/text-to-sign', '/conversation', '/classes', '/analytics'];
    // the 360 px pass is repeated with a wide fallback font: CI runners' fonts are wider than local ones
    for (const [viewport, font] of [[{ width: 360, height: 740 }], [{ width: 360, height: 740 }, 'DejaVu Sans'], [{ width: 768, height: 1024 }], [{ width: 1280, height: 800 }]]) {
      const { page, ctx, errors } = await newPage(browser, srv.base, { viewport });
      if (font) await page.addInitScript((f) => document.addEventListener('DOMContentLoaded', () => { const st = document.createElement('style'); st.textContent = `*{font-family:'${f}' !important}`; document.head.append(st); }), font);
      await login(page);
      for (const route of routes) {
        await page.goto(route);
        await page.getByRole('heading', { level: 1 }).waitFor();
        const r = await page.evaluate(() => {
          const visible = (el) => el.offsetParent !== null || getComputedStyle(el).position === 'fixed';
          const named = (el) => (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title') || '').trim()
            || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || el.closest('label');
          return {
            lang: document.documentElement.lang,
            overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            imgsNoAlt: [...document.images].filter((i) => !i.hasAttribute('alt')).length,
            unlabeled: [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
              .filter((el) => visible(el) && !named(el)).map((el) => el.outerHTML.slice(0, 80)),
            emptyLinks: [...document.querySelectorAll('a[href]')].filter((a) => visible(a) && !a.textContent.trim() && !a.getAttribute('aria-label')).length,
            main: !!document.querySelector('main#main'),
            wide: [...document.querySelectorAll('main *')].filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
              .slice(-3).map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} "${el.textContent.trim().slice(0, 30)}" right=${Math.round(el.getBoundingClientRect().right)}`),
          };
        });
        const where = `${route} @${viewport.width}px${font ? ` (${font})` : ''}`;
        assert.ok(r.lang, `html lang missing ${where}`);
        assert.ok(r.overflow <= 1, `${where} overflows by ${r.overflow}px: ${r.wide.join(' | ')}`);
        assert.equal(r.imgsNoAlt, 0, `images without alt ${where}`);
        assert.deepEqual(r.unlabeled, [], `unlabelled form controls ${where}`);
        assert.equal(r.emptyLinks, 0, `links without a name ${where}`);
        assert.ok(r.main, `main landmark ${where}`);
      }
      assert.deepEqual(errors, []);
      await ctx.close();
    }
  });

  test('mobile layout has no horizontal scroll and a working nav drawer', async () => {
    const { page, ctx } = await newPage(browser, srv.base, { viewport: { width: 390, height: 844 } });
    for (const route of ['/', '/signs', '/live', '/dataset']) {
      await page.goto(route);
      await page.getByRole('heading', { level: 1 }).waitFor();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 1, `${route} overflows by ${overflow}px`);
    }
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await page.getByRole('dialog', { name: 'Navigation' }).getByRole('link', { name: 'Sign Explorer' }).click();
    await page.waitForURL(/\/signs$/);
    await ctx.close();
  });
});

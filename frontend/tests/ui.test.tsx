import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { Heatmap, ProbBars, Segmented } from '../src/components/charts.tsx';
import { Badge, Button, Empty, Meter, Notice, StatusBadge, Stat, fmt } from '../src/components/ui.tsx';
import { match } from '../src/lib/router.tsx';
import { can, createStore, type User } from '../src/lib/store.ts';

const user = (roles: string[]): User => ({ id: 1, email: 'a@b.c', display_name: 'A', roles, preferred_language: 'en', settings: {} });

test('router matches static and parameterised paths', () => {
  assert.deepEqual(match('/signs/:id', '/signs/ISL001'), { id: 'ISL001' });
  assert.deepEqual(match('/', '/'), {});
  assert.equal(match('/signs/:id', '/signs'), null);
  assert.equal(match('/admin', '/ai'), null);
  assert.deepEqual(match('/signs/:id', '/signs/ISL%20X'), { id: 'ISL X' });
});

test('permission hints mirror server roles', () => {
  assert.equal(can(null, 'signs:write'), false);
  assert.equal(can(user(['learner']), 'signs:write'), false);
  assert.equal(can(user(['linguist']), 'signs:review'), true);
  assert.equal(can(user(['data_curator']), 'dataset:write'), true);
  assert.equal(can(user(['researcher']), 'models:promote'), false);
  assert.equal(can(user(['admin']), 'models:promote'), true);
});

test('store notifies subscribers and merges state', () => {
  const s = createStore({ a: 1, b: 2 });
  let calls = 0;
  const off = s.subscribe(() => calls++);
  s.set({ a: 5 });
  s.set((x) => ({ b: x.a + 1 }));
  off();
  s.set({ a: 0 });
  assert.deepEqual(s.get(), { a: 0, b: 6 });
  assert.equal(calls, 2);
});

test('status badges have human labels for every prediction state', () => {
  for (const [state, label] of [['recognized', 'Recognized'], ['uncertain', 'Uncertain'], ['unknown', 'Unknown sign'], ['insufficient_input', 'Insufficient input'], ['model_unavailable', 'Model unavailable'], ['camera_unavailable', 'Camera unavailable']]) {
    assert.match(renderToStaticMarkup(<StatusBadge status={state} />), new RegExp(label));
  }
  assert.match(renderToStaticMarkup(<StatusBadge status="something_new" />), /something_new/);
});

test('buttons expose busy state and disable while loading', () => {
  const html = renderToStaticMarkup(<Button loading>Save</Button>);
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /disabled=""/);
});

test('meter is an accessible progressbar', () => {
  const html = renderToStaticMarkup(<Meter label="Verified" value={3} max={200} />);
  assert.match(html, /role="progressbar"/);
  assert.match(html, /aria-valuenow="3"/);
  assert.match(html, /aria-valuemax="200"/);
});

test('empty, notice, stat and badge render their content', () => {
  assert.match(renderToStaticMarkup(<Empty title="Nothing here">Hint</Empty>), /Nothing here.*Hint/s);
  assert.match(renderToStaticMarkup(<Notice tone="warn" title="Careful" />), /role="note"/);
  assert.match(renderToStaticMarkup(<Stat label="Slots" value={200} />), /200/);
  assert.match(renderToStaticMarkup(<Badge tone="ok">ok</Badge>), /emerald/);
});

test('charts provide text alternatives', () => {
  const seg = renderToStaticMarkup(<Segmented label="Readiness" parts={[{ label: 'no data', value: 200, color: '#000' }]} />);
  assert.match(seg, /aria-label="no data: 200"/);
  const hm = renderToStaticMarkup(<Heatmap label="CM" labels={['A', 'B']} matrix={[[2, 0], [1, 3]]} />);
  assert.match(hm, /true A → predicted A: 2/);
  const pb = renderToStaticMarkup(<ProbBars items={[{ label: 'Hello', p: 0.5 }]} />);
  assert.match(pb, /50\.0%/);
});

test('formatters never invent values', () => {
  assert.equal(fmt.pct(undefined), '-');
  assert.equal(fmt.pct(Number.NaN), '-');
  assert.equal(fmt.pct(0.1234), '12.3%');
  assert.equal(fmt.bytes(0), '-');
  assert.equal(fmt.date(null), '-');
});

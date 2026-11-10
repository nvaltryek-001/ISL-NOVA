import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Frame } from '../src/lib/features';
import { SignSegmenter } from '../src/lib/segmenter';

const hand = (x: number, y: number) => Array.from({ length: 21 }, () => [x, y, 0]);
const frame = (x: number | null, y = 0.5): Frame => ({ left: null, right: x === null ? null : hand(x, y), pose: null });

function run(script: (t: number) => Frame, ms: number, fps = 25) {
  const s = new SignSegmenter();
  const out = [];
  for (let t = 0; t <= ms; t += 1000 / fps) {
    const seg = s.push(script(t), t);
    if (seg) out.push(seg);
  }
  return out;
}

test('two signs separated by a rest become two segments', () => {
  const move = (t: number, t0: number) => 0.3 + 0.2 * Math.sin(((t - t0) / 1000) * 2 * Math.PI);
  const segs = run((t) => {
    if (t < 500) return frame(0.3);                 // hands resting
    if (t < 1700) return frame(move(t, 500));       // sign 1
    if (t < 2700) return frame(0.3);                // rest
    if (t < 3900) return frame(move(t, 2700), 0.6); // sign 2
    return frame(null);                             // hands leave
  }, 5000);
  assert.equal(segs.length, 2);
  assert.ok(segs[0].start < 700 && segs[0].end > 1600 && segs[0].end < 2700, JSON.stringify(segs.map((s) => [s.start, s.end])));
  assert.ok(segs[1].start > 2400 && segs[1].reason === 'hands_left');
  for (const s of segs) assert.ok(s.frames.length >= 20);
});

test('still hands, no hands and short twitches produce nothing; long signing is cut at the maximum', () => {
  assert.equal(run(() => frame(0.4), 3000).length, 0);
  assert.equal(run(() => frame(null), 3000).length, 0);
  assert.equal(run((t) => frame(t > 1000 && t < 1250 ? 0.3 + 0.05 * Math.sin(((t - 1000) / 250) * Math.PI) : 0.3), 3000).length, 0);
  const long = run((t) => frame(0.3 + 0.2 * Math.sin((t / 1000) * 2 * Math.PI)), 8000);
  assert.ok(long.length >= 2 && long[0].reason === 'max_length');
});

// Splits a continuous landmark stream into candidate signs at pauses.
// A segment opens when a hand appears or the wrists start moving, and closes when
// the hands rest or leave the frame for REST_MS (or after MAX_MS). Each closed
// segment is classified on its own, so a sequence of signs is read one sign at a
// time instead of from overlapping sliding windows. The result is a *recognized
// word sequence*, not a translation: ISL grammar is not modelled.
import type { Frame } from './features';

export type Timed = { f: Frame; t: number };
export type Segment = { frames: Timed[]; start: number; end: number; reason: 'rest' | 'hands_left' | 'max_length' };

export const SEG = { START_SPEED: 0.06, STOP_SPEED: 0.025, REST_MS: 450, MIN_MS: 500, MAX_MS: 3500, PRE_MS: 200 };

function wrists(f: Frame): [number, number][] {
  return [f.left, f.right].filter((h): h is number[][] => !!h).map((h) => [h[0][0], h[0][1]]);
}

/** Wrist speed in image widths per second between two frames (0 when no common hand). */
export function speed(a: Timed, b: Timed): number {
  const dt = Math.max(1, b.t - a.t) / 1000;
  const wa = wrists(a.f);
  const wb = wrists(b.f);
  if (!wa.length || !wb.length) return 0;
  const n = Math.min(wa.length, wb.length);
  let d = 0;
  for (let i = 0; i < n; i++) d = Math.max(d, Math.hypot(wb[i][0] - wa[i][0], wb[i][1] - wa[i][1]));
  return d / dt;
}

export class SignSegmenter {
  private history: Timed[] = [];
  private open: Timed[] | null = null;
  private openAt = 0;
  private movingFrom = 0;
  private quietSince: number | null = null;
  private smooth = 0;

  /** Feed one frame; returns a finished segment when one closes. */
  push(f: Frame, t: number): Segment | null {
    const cur = { f, t };
    const prev = this.history.at(-1);
    const v = prev ? speed(prev, cur) : 0;
    this.smooth = 0.3 * this.smooth + 0.7 * v;
    this.history.push(cur);
    while (this.history.length && t - this.history[0].t > SEG.PRE_MS + 50) this.history.shift();
    const hands = !!(f.left || f.right);

    if (!this.open) {
      if (hands && this.smooth >= SEG.START_SPEED) {
        this.open = this.history.slice();  // include a little lead-in
        this.openAt = this.open[0].t;
        this.movingFrom = t;
        this.quietSince = null;
      }
      return null;
    }
    this.open.push(cur);
    const quiet = !hands || this.smooth < SEG.STOP_SPEED;
    if (quiet) this.quietSince ??= t; else this.quietSince = null;
    const dur = t - this.movingFrom;
    let reason: Segment['reason'] | null = null;
    if (dur >= SEG.MAX_MS) reason = 'max_length';
    else if (this.quietSince !== null && t - this.quietSince >= SEG.REST_MS) reason = hands ? 'rest' : 'hands_left';
    if (!reason) return null;
    const frames = this.open;
    const activeEnd = reason === 'max_length' ? t : (this.quietSince ?? t);
    this.open = null;
    this.quietSince = null;
    if (activeEnd - this.movingFrom < SEG.MIN_MS) return null;  // a twitch, not a sign
    return { frames, start: this.openAt, end: t, reason };
  }

  reset() { this.history = []; this.open = null; this.quietSince = null; this.smooth = 0; }
}

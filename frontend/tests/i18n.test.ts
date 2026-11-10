import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { coverage, translate } from '../src/i18n/index.ts';
import { STRINGS } from '../src/i18n/strings.ts';

test('every UI string has Hindi and Kannada text in the right script', () => {
  for (const [en, [hi, kn]] of Object.entries(STRINGS)) {
    assert.ok(hi && kn, `missing translation for "${en}"`);
    assert.match(hi, /[ऀ-ॿ]|^[\dA-Z· ()/.-]+/, `Hindi for "${en}" has no Devanagari`);
    assert.match(kn, /[ಀ-೿]|^[\dA-Z· ()/.-]+/, `Kannada for "${en}" has no Kannada script`);
  }
  const c = coverage();
  assert.equal(c.hi, c.keys); assert.equal(c.kn, c.keys);
});

test('translate falls back to English and never returns blanks', () => {
  assert.equal(translate('Live Recognition', 'hi'), 'लाइव पहचान');
  assert.equal(translate('Live Recognition', 'kn'), 'ನೇರ ಗುರುತಿಸುವಿಕೆ');
  assert.equal(translate('Some new string', 'kn'), 'Some new string');
  assert.equal(translate('Dashboard', 'en'), 'Dashboard');
});

test('page titles, kickers, card titles and button labels are covered', () => {
  const pat = /(?:title|kicker|subtitle|label)=["']([^"'{}]{2,80})["']/g;
  const btn = /<Button[^>]*>([A-Za-z][^<{]{1,50})<\/Button>/g;
  const used = new Set<string>();
  const walk = (d: string) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p); else if (p.endsWith('.tsx')) {
      const s = fs.readFileSync(p, 'utf8');
      for (const m of s.matchAll(pat)) used.add(m[1]);
      for (const m of s.matchAll(btn)) used.add(m[1].trim());
    }
  });
  walk(path.join(import.meta.dirname, '..', 'src'));
  const missing = [...used].filter((s) => !(s in STRINGS));
  const share = 1 - missing.length / used.size;
  // report and enforce a high floor; new strings must be added to src/i18n/strings.ts
  assert.ok(share >= 0.9, `only ${(share * 100).toFixed(1)} % of ${used.size} UI strings translated; missing e.g. ${missing.slice(0, 10).join(' | ')}`);
});

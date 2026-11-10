// Match typed or spoken text (en/hi/kn) to vocabulary signs, longest phrase first.
// The result is a sequence of individual signs, NOT a grammatical ISL translation.
import { api } from './api';

export type Match = { text: string; sign_id: string | null; label?: string; status?: string };
type Hit = { sign_id: string; canonical_sign_name: string; verification_status: string; translations: Record<string, { text: string }> };

const norm = (s: string) => s.toLocaleLowerCase().replace(/[.,!?।॥"“”'’()]/g, '').trim();

async function exact(phrase: string): Promise<Hit | null> {
  const r = await api<{ items: Hit[] }>(`/signs?size=10&q=${encodeURIComponent(phrase)}`);
  const p = norm(phrase);
  return r.items.find((h) => norm(h.canonical_sign_name) === p
    || Object.values(h.translations ?? {}).some((t) => t.text && norm(t.text).split(/\s*\(/)[0] === p)) ?? null;
}

export async function textToSigns(text: string, maxWords = 3): Promise<Match[]> {
  const words = text.split(/\s+/).map((w) => w.trim()).filter(Boolean);
  const out: Match[] = [];
  let i = 0;
  while (i < words.length) {
    let found: { hit: Hit; n: number } | null = null;
    for (let n = Math.min(maxWords, words.length - i); n >= 1 && !found; n--) {
      const hit = await exact(words.slice(i, i + n).join(' '));
      if (hit) found = { hit, n };
    }
    if (found) {
      out.push({ text: words.slice(i, i + found.n).join(' '), sign_id: found.hit.sign_id, label: found.hit.canonical_sign_name, status: found.hit.verification_status });
      i += found.n;
    } else {
      out.push({ text: words[i], sign_id: null });
      i += 1;
    }
  }
  return out;
}

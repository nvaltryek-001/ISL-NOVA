// Lightweight i18n: English is the key; Hindi and Kannada come from STRINGS.
// Missing keys fall back to English so the UI never shows blanks.
import { prefs, usePrefs } from '../lib/store';
import { STRINGS } from './strings';

export type Lang = 'en' | 'hi' | 'kn';
export const LANG_NAMES: Record<Lang, string> = { en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ' };
export const SPEECH_LANG: Record<Lang, string> = { en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN' };

export function translate(s: string, lang: Lang): string {
  if (lang === 'en' || !s) return s;
  const hit = STRINGS[s];
  return hit ? hit[lang === 'hi' ? 0 : 1] : s;
}

/** Translate outside React (uses the current preference). */
export const t = (s: string) => translate(s, prefs.get().language);

/** Hook: returns a translator bound to the current interface language (re-renders on change). */
export function useT(): (s: string) => string {
  const { language } = usePrefs();
  return (s: string) => translate(s, language);
}

/** Translate a ReactNode only if it is a plain string. */
export function tr<T>(node: T, tf: (s: string) => string): T {
  return (typeof node === 'string' ? tf(node) : node) as T;
}

/** Share of keys present for a language (used by the coverage test and the Settings page). */
export function coverage(): { keys: number; hi: number; kn: number } {
  const v = Object.values(STRINGS);
  return { keys: v.length, hi: v.filter((x) => x[0]).length, kn: v.filter((x) => x[1]).length };
}

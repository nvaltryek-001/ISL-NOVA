// Text-to-speech via the Web Speech API, with honest availability reporting.
const LANG: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN' };

export function speechSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export function voiceFor(lang: string): SpeechSynthesisVoice | null {
  if (!speechSupported()) return null;
  const want = LANG[lang] ?? lang;
  const vs = speechSynthesis.getVoices();
  return vs.find((v) => v.lang === want) ?? vs.find((v) => v.lang.startsWith(want.slice(0, 2))) ?? null;
}

export function speak(text: string, lang = 'en', rate = 1): { ok: boolean; reason?: string } {
  if (!speechSupported()) return { ok: false, reason: 'Speech synthesis is not supported in this browser.' };
  if (!text.trim()) return { ok: false, reason: 'Nothing to speak.' };
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG[lang] ?? lang;
  u.rate = rate;
  const v = voiceFor(lang);
  if (v) u.voice = v;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
  return v || lang === 'en' ? { ok: true } : { ok: true, reason: `No ${u.lang} voice installed; your browser may use a default voice.` };
}

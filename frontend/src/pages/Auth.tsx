import { type FormEvent, useState } from 'react';
import { Icon } from '../components/icons';
import { Button, ErrorNote, Field, Input } from '../components/ui';
import { api, type ApiError } from '../lib/api';
import { clearCache } from '../lib/query';
import { Link, navigate, useLocation } from '../lib/router';
import { auth, type User } from '../lib/store';

// client-side checks for fast feedback; the API validates the same rules (Pydantic)
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export function validateRegistration(f: { display_name: string; email: string; password: string }): Record<string, string> {
  const e: Record<string, string> = {};
  const name = f.display_name.trim();
  if (!name) e.display_name = 'Enter your name';
  else if (name.length > 120) e.display_name = 'Use at most 120 characters';
  if (!EMAIL.test(f.email.trim())) e.email = 'Enter a valid email address';
  if (f.password.length < 10) e.password = 'Use at least 10 characters';
  return e;
}

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { search } = useLocation();
  const next = search.get('next') || '/';
  const [form, setForm] = useState({ email: '', password: '', display_name: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === 'register') {
      const v = validateRegistration(form);
      if (Object.keys(v).length) { setErrors(v); return; }
    }
    setErrors({});
    setBusy(true);
    try {
      const body = mode === 'login' ? { email: form.email, password: form.password } : form;
      const res = await api<{ access_token: string; user: User }>(`/auth/${mode}`, { body });
      clearCache();
      auth.login(res.access_token, res.user);
      navigate(next.startsWith('/') && !next.startsWith('//') ? next : '/', true);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden border-r border-ink-800 bg-ink-950 lg:block">
        <div className="grid-bg absolute inset-0 opacity-60" />
        <div className="absolute -left-24 top-1/4 size-[28rem] rounded-full bg-nova-600/20 blur-3xl" />
        <div className="absolute bottom-0 right-0 size-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3"><img src="/favicon.svg" alt="" className="size-10" /><span className="font-display text-xl font-semibold">ISL NOVA</span></div>
          <div className="max-w-md">
            <h1 className="font-display text-4xl font-semibold leading-tight text-fg">Beyond gestures.<br /><span className="bg-gradient-to-r from-nova-300 to-signal bg-clip-text text-transparent">Towards understanding.</span></h1>
            <p className="mt-4 text-ink-300">An open platform for Indian Sign Language recognition, learning and consent-first dataset building.</p>
            <ul className="mt-8 space-y-3 text-sm text-ink-300">
              {['200 vocabulary slots with traceable, licensed sources', 'Signer-independent evaluation, no fabricated accuracy', 'Video stays on your device during live recognition'].map((t) => (
                <li key={t} className="flex gap-2"><Icon name="check" className="mt-0.5 text-signal" />{t}</li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-ink-500">Vocabulary derived from INCLUDE (Sridhar et al., ACM MM 2020), CC BY 4.0.</p>
        </div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" noValidate>
          <div>
            <Link to="/" className="mb-8 inline-flex items-center gap-2 text-sm text-ink-400 hover:text-fg lg:hidden"><img src="/favicon.svg" alt="" className="size-7" />ISL NOVA</Link>
            <h2 className="font-display text-2xl font-semibold text-fg">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
            <p className="muted mt-1 text-sm">{mode === 'login' ? 'Sign in to save history, progress and bookmarks.' : 'New accounts start with the learner role.'}</p>
          </div>
          <ErrorNote error={error} />
          {mode === 'register' && (
            <Field label="Name" error={errors.display_name}>{(id) => <Input id={id} autoComplete="name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />}</Field>
          )}
          <Field label="Email" error={errors.email}>{(id) => <Input id={id} type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}</Field>
          <Field label="Password" error={errors.password} hint={mode === 'register' ? 'At least 10 characters.' : undefined}>
            {(id) => <Input id={id} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}
          </Field>
          <Button variant="primary" className="w-full" loading={busy} type="submit">{mode === 'login' ? 'Sign in' : 'Create account'}</Button>
          <p className="text-center text-sm text-ink-400">
            {mode === 'login' ? <>No account? <Link to={`/register?next=${encodeURIComponent(next)}`} className="text-nova-300 hover:underline">Create one</Link></>
              : <>Already registered? <Link to={`/login?next=${encodeURIComponent(next)}`} className="text-nova-300 hover:underline">Sign in</Link></>}
          </p>
          <p className="text-center"><Link to="/" className="text-xs text-ink-500 hover:text-ink-300">Continue without an account</Link></p>
        </form>
      </div>
    </div>
  );
}

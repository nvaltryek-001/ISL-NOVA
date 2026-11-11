import { type FormEvent, useState } from 'react';
import { HandArt } from '../components/HandArt';
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
  const [form, setForm] = useState({ email: '', password: '', display_name: '', otp: '' });
  const [needOtp, setNeedOtp] = useState(false);
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
      const body = mode === 'login' ? { email: form.email, password: form.password, ...(needOtp ? { otp: form.otp } : {}) }
        : { email: form.email, password: form.password, display_name: form.display_name };
      const res = await api<{ access_token: string; refresh_token?: string; user: User }>(`/auth/${mode}`, { body });
      clearCache();
      auth.login(res.access_token, res.user, res.refresh_token ?? null);
      navigate(next.startsWith('/') && !next.startsWith('//') ? next : '/', true);
    } catch (err) {
      const e2 = err as ApiError;
      if (e2.code === 'otp_required') { setNeedOtp(true); setError(null); } else setError(e2);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden border-r border-ink-800 bg-ink-950 lg:block">
        <div className="grid-bg absolute inset-0 opacity-60" />
        <span className="orb -left-24 top-1/4 size-[28rem] bg-nova-600/25" aria-hidden />
        <span className="orb bottom-0 right-0 size-72 bg-cyan-500/20 [animation-delay:-7s]" aria-hidden />
        <HandArt className="absolute -bottom-6 -right-8 w-[300px] opacity-60" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3"><img src="/favicon.svg" alt="" className="float size-10" /><span className="font-display text-xl font-semibold">ISL NOVA</span></div>
          <div className="stagger max-w-md">
            <h1 className="font-display text-4xl font-semibold leading-tight text-fg">Beyond gestures.<br /><span className="text-gradient">Towards understanding.</span></h1>
            <p className="mt-4 text-ink-300">Recognise, learn and practise Indian Sign Language in English, हिन्दी and ಕನ್ನಡ.</p>
            <ul className="mt-8 space-y-3 text-sm text-ink-300">
              {['200 signs with meanings in three languages', 'Default model: 95.1 % top-1 on the INCLUDE test split', 'Your camera video stays on your device'].map((t) => (
                <li key={t} className="flex gap-2"><Icon name="check" className="mt-0.5 text-signal" />{t}</li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-ink-500">Vocabulary derived from INCLUDE (Sridhar et al., ACM MM 2020), CC BY 4.0.</p>
        </div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="page-enter w-full max-w-sm space-y-5" noValidate>
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
          {mode === 'login' && needOtp && (
            <Field label="Authenticator code" hint="6 digits from your authenticator app.">{(id) => <Input id={id} inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={6} value={form.otp} onChange={(e) => setForm({ ...form, otp: e.target.value.replace(/\D/g, '') })} />}</Field>
          )}
          <Button variant="primary" className="w-full" loading={busy} type="submit">{mode === 'login' ? 'Sign in' : 'Create account'}</Button>
          <p className="text-center text-sm text-ink-400">
            {mode === 'login' ? <>No account? <Link to={`/register?next=${encodeURIComponent(next)}`} className="text-nova-300 hover:underline">Create one</Link></>
              : <>Already registered? <Link to={`/login?next=${encodeURIComponent(next)}`} className="text-nova-300 hover:underline">Sign in</Link></>}
          </p>
          {mode === 'login' && <p className="text-center text-sm"><Link to="/reset-password" className="text-ink-400 hover:underline">Have a reset code?</Link></p>}
          <p className="text-center"><Link to="/" className="text-xs text-ink-500 hover:text-ink-300">Continue without an account</Link></p>
        </form>
      </div>
    </div>
  );
}

export function ResetPasswordPage() {
  const [form, setForm] = useState({ code: '', new_password: '' });
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api('/auth/reset-password', { body: { code: form.code.trim(), new_password: form.new_password } });
      setDone(true);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5" noValidate>
        <div>
          <h1 className="font-display text-2xl font-semibold text-fg">Reset your password</h1>
          <p className="muted mt-1 text-sm">Enter the one-time code an administrator gave you. It expires 30 minutes after it was issued.</p>
        </div>
        <ErrorNote error={error} />
        {done ? (
          <p role="status" className="text-sm">Password changed and all earlier sessions signed out. <Link to="/login" className="text-nova-300 hover:underline">Sign in</Link></p>
        ) : (
          <>
            <Field label="Reset code">{(id) => <Input id={id} autoComplete="one-time-code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />}</Field>
            <Field label="New password" hint="At least 10 characters.">{(id) => <Input id={id} type="password" autoComplete="new-password" required value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} />}</Field>
            <Button variant="primary" className="w-full" loading={busy} disabled={form.new_password.length < 10 || form.code.trim().length < 10} type="submit">Set new password</Button>
          </>
        )}
        <p className="text-center"><Link to="/login" className="text-xs text-ink-500 hover:text-ink-300">Back to sign in</Link></p>
      </form>
    </div>
  );
}

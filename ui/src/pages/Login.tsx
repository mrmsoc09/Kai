import { FormEvent, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { authService } from '../api';
import { useAuth } from '../hooks/useAuth';

interface LocationState {
  from?: string;
}

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { auth, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as LocationState | undefined)?.from ?? '/dashboard';

  if (auth.isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!username.trim() || !password) {
      setError('Username and password are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const token = await authService.login({
        username: username.trim(),
        password,
      });

      let currentUser = null;
      try {
        currentUser = await authService.me();
      } catch {
        currentUser = {
          id: token.user_id,
          role: token.role,
          tenantId: token.tenant_id,
        };
      }

      login(token.access_token, currentUser);
      navigate(redirectTo, { replace: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to sign in.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/80 p-6">
        <h1 className="text-lg font-semibold text-slate-100">Kai Operator Login</h1>
        <p className="mt-1 text-sm text-slate-400">Sign in using your platform credentials.</p>

        <label className="mt-4 block text-sm text-slate-300">
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
            placeholder="operator"
            autoComplete="username"
          />
        </label>

        <label className="mt-3 block text-sm text-slate-300">
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>

        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-4 w-full rounded bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-60"
        >
          {isSubmitting ? 'Signing In...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}

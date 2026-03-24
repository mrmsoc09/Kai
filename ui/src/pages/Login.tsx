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
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [bootstrapToken, setBootstrapToken] = useState<string | null>(null);
  const [pendingUsername, setPendingUsername] = useState<string | null>(null);
  const [needsInitialPassword, setNeedsInitialPassword] = useState(false);
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

    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setError('Username is required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const token = await authService.login({
        username: normalizedUsername,
        password,
      });

      if (token.password_setup_required) {
        setBootstrapToken(token.access_token);
        setPendingUsername(normalizedUsername);
        setNeedsInitialPassword(true);
        setPassword('');
        return;
      }

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

  const handleInitialPasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!bootstrapToken || !pendingUsername) {
      setError('Initial password setup session is missing. Sign in again.');
      return;
    }
    if (!newPassword) {
      setError('New password is required.');
      return;
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      await authService.setInitialPassword(bootstrapToken, newPassword);
      const token = await authService.login({
        username: pendingUsername,
        password: newPassword,
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
      setError(submitError instanceof Error ? submitError.message : 'Unable to set initial password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <form
        onSubmit={needsInitialPassword ? handleInitialPasswordSubmit : handleSubmit}
        className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900/80 p-6"
      >
        <h1 className="text-lg font-semibold text-slate-100">Kai Operator Login</h1>
        <p className="mt-1 text-sm text-slate-400">
          {needsInitialPassword ? 'Set your initial password for k1-admin.' : 'Sign in using your platform credentials.'}
        </p>

        {!needsInitialPassword ? (
          <>
            <label className="mt-4 block text-sm text-slate-300">
              Username
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
                placeholder="k1-admin"
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
                placeholder="(blank on first k1-admin login)"
                autoComplete="current-password"
              />
            </label>
          </>
        ) : (
          <>
            <label className="mt-4 block text-sm text-slate-300">
              New Password
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
                placeholder="Choose a strong password"
                autoComplete="new-password"
              />
            </label>

            <label className="mt-3 block text-sm text-slate-300">
              Confirm New Password
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
                placeholder="Re-enter new password"
                autoComplete="new-password"
              />
            </label>
          </>
        )}

        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-4 w-full rounded bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-60"
        >
          {isSubmitting ? 'Working...' : needsInitialPassword ? 'Set Password' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}

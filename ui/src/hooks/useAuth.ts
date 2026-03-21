import { useMemo } from 'react';
import { useAppStore } from '../store/appStore';
import { hasAnyRole } from '../utils/auth';
import type { AuthUser, UserRole } from '../types';

export function useAuth() {
  const auth = useAppStore((state) => state.auth);
  const setAuth = useAppStore((state) => state.setAuth);
  const setAuthUser = useAppStore((state) => state.setAuthUser);
  const clearAuth = useAppStore((state) => state.clearAuth);
  const currentRole = auth.user?.role;

  const permissions = useMemo(
    () => ({
      canOperateMissions: hasAnyRole(currentRole, ['analyst', 'admin']),
      canReviewGovernance: hasAnyRole(currentRole, ['operator', 'analyst', 'admin']),
      canDecideGovernance: hasAnyRole(currentRole, ['analyst', 'admin']),
      canRunSimulation: hasAnyRole(currentRole, ['analyst', 'admin']),
      canViewSystemStatus: hasAnyRole(currentRole, ['admin']),
    }),
    [currentRole],
  );

  return {
    auth,
    permissions,
    login: (token: string, user?: AuthUser | null) => setAuth(token, user),
    updateAuthUser: (user: AuthUser | null) => setAuthUser(user),
    hasRole: (roles: UserRole[]) => hasAnyRole(currentRole, roles),
    logout: clearAuth,
  };
}

import type { AuthUser, UserRole } from '../types';

interface TokenClaims {
  sub?: string;
  tid?: string;
  rol?: string;
  roles?: string[];
}

const rolePriority: UserRole[] = ['viewer', 'operator', 'analyst', 'admin'];

const toBase64 = (value: string): string => {
  const padding = '='.repeat((4 - (value.length % 4 || 4)) % 4);
  return `${value}${padding}`.replace(/-/g, '+').replace(/_/g, '/');
};

export const isUserRole = (value: string): value is UserRole => rolePriority.includes(value as UserRole);

export const decodeTokenClaims = (token: string): TokenClaims | null => {
  const segments = token.split('.');
  if (segments.length < 2) {
    return null;
  }

  try {
    const payload = window.atob(toBase64(segments[1]));
    return JSON.parse(payload) as TokenClaims;
  } catch {
    return null;
  }
};

export const roleFromClaims = (claims: TokenClaims | null): UserRole | null => {
  if (!claims) {
    return null;
  }

  if (claims.rol && isUserRole(claims.rol)) {
    return claims.rol;
  }

  if (Array.isArray(claims.roles)) {
    const normalizedRoles = claims.roles.filter(isUserRole);
    if (normalizedRoles.length > 0) {
      const sorted = [...normalizedRoles].sort((left, right) => rolePriority.indexOf(right) - rolePriority.indexOf(left));
      return sorted[0];
    }
  }

  return null;
};

export const authUserFromToken = (token: string): AuthUser | null => {
  const claims = decodeTokenClaims(token);
  if (!claims?.sub) {
    return null;
  }

  const role = roleFromClaims(claims);
  if (!role || !claims.tid) {
    return null;
  }

  return {
    id: claims.sub,
    role,
    tenantId: claims.tid,
  };
};

export const hasAnyRole = (currentRole: UserRole | undefined, acceptedRoles: UserRole[]): boolean => {
  if (!currentRole) {
    return false;
  }
  return acceptedRoles.includes(currentRole);
};

export type UserRole = 'viewer' | 'operator' | 'analyst' | 'admin';

export interface AuthUser {
  id: string;
  username?: string;
  email?: string | null;
  fullName?: string | null;
  role: UserRole;
  tenantId: string;
  isActive?: boolean;
  isSuperuser?: boolean;
}

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  user: AuthUser | null;
}

export interface LoginInput {
  username: string;
  password: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user_id: string;
  tenant_id: string;
  role: UserRole;
  password_setup_required?: boolean;
}

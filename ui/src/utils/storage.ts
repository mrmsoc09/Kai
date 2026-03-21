import { appConfig } from './config';
import type { AuthUser } from '../types';

export const tokenStorage = {
  getToken: (): string | null => localStorage.getItem(appConfig.authTokenStorageKey),
  setToken: (token: string): void => localStorage.setItem(appConfig.authTokenStorageKey, token),
  clearToken: (): void => localStorage.removeItem(appConfig.authTokenStorageKey),
};

export const authUserStorage = {
  getUser: (): AuthUser | null => {
    const raw = localStorage.getItem(appConfig.authUserStorageKey);
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      localStorage.removeItem(appConfig.authUserStorageKey);
      return null;
    }
  },
  setUser: (user: AuthUser | null): void => {
    if (!user) {
      localStorage.removeItem(appConfig.authUserStorageKey);
      return;
    }
    localStorage.setItem(appConfig.authUserStorageKey, JSON.stringify(user));
  },
  clearUser: (): void => localStorage.removeItem(appConfig.authUserStorageKey),
};

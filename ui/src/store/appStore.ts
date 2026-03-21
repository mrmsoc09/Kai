import { create } from 'zustand';
import type { AuthState, AuthUser, SystemStatus, WebSocketConnectionState } from '../types';
import { authUserStorage, tokenStorage } from '../utils/storage';
import { authUserFromToken } from '../utils/auth';

interface AppStore {
  auth: AuthState;
  currentMissionId: string | null;
  systemStatus: SystemStatus | null;
  webSocketState: WebSocketConnectionState;
  setAuth: (token: string, user?: AuthUser | null) => void;
  setAuthUser: (user: AuthUser | null) => void;
  clearAuth: () => void;
  setCurrentMission: (missionId: string | null) => void;
  setSystemStatus: (status: SystemStatus) => void;
  setWebSocketState: (state: WebSocketConnectionState) => void;
}

const initialToken = tokenStorage.getToken();
const initialStoredUser = authUserStorage.getUser();
const initialTokenUser = initialToken ? authUserFromToken(initialToken) : null;
const initialUser = initialStoredUser ?? initialTokenUser;

export const useAppStore = create<AppStore>((set) => ({
  auth: {
    token: initialToken,
    isAuthenticated: Boolean(initialToken),
    user: initialUser,
  },
  currentMissionId: null,
  systemStatus: null,
  webSocketState: 'idle',
  setAuth: (token, user) => {
    const resolvedUser = user ?? authUserFromToken(token);
    tokenStorage.setToken(token);
    authUserStorage.setUser(resolvedUser);
    set({
      auth: {
        token,
        isAuthenticated: true,
        user: resolvedUser,
      },
    });
  },
  setAuthUser: (user) => {
    authUserStorage.setUser(user);
    set((state) => ({
      auth: {
        ...state.auth,
        user,
      },
    }));
  },
  clearAuth: () => {
    tokenStorage.clearToken();
    authUserStorage.clearUser();
    set({
      auth: {
        token: null,
        isAuthenticated: false,
        user: null,
      },
    });
  },
  setCurrentMission: (currentMissionId) => set({ currentMissionId }),
  setSystemStatus: (systemStatus) => set({ systemStatus }),
  setWebSocketState: (webSocketState) => set({ webSocketState }),
}));

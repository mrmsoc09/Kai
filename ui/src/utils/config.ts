export interface AppConfig {
  apiBaseUrl: string;
  webSocketBaseUrl: string;
  missionEventsPath: string;
  authTokenStorageKey: string;
  authUserStorageKey: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';
const WEBSOCKET_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? '/ws';
const MISSION_EVENTS_PATH = import.meta.env.VITE_MISSION_EVENTS_WS_PATH ?? '';
const AUTH_TOKEN_STORAGE_KEY = import.meta.env.VITE_AUTH_TOKEN_STORAGE_KEY ?? 'kai.auth.token';
const AUTH_USER_STORAGE_KEY = import.meta.env.VITE_AUTH_USER_STORAGE_KEY ?? 'kai.auth.user';

export const appConfig: AppConfig = {
  apiBaseUrl: API_BASE_URL,
  webSocketBaseUrl: WEBSOCKET_BASE_URL,
  missionEventsPath: MISSION_EVENTS_PATH,
  authTokenStorageKey: AUTH_TOKEN_STORAGE_KEY,
  authUserStorageKey: AUTH_USER_STORAGE_KEY,
};

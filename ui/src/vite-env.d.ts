/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WS_BASE_URL?: string;
  readonly VITE_MISSION_EVENTS_WS_PATH?: string;
  readonly VITE_AUTH_TOKEN_STORAGE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

import type { ApiErrorPayload } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
const ACCESS_TOKEN_STORAGE_KEY = "k1_access_token";
let devBootstrapPromise: Promise<string | null> | null = null;

export class ApiError extends Error {
  status: number;
  payload: ApiErrorPayload;

  constructor(status: number, payload: ApiErrorPayload = {}, fallbackMessage?: string) {
    super(
      typeof payload.detail === "string"
        ? payload.detail
        : typeof payload.message === "string"
          ? payload.message
          : fallbackMessage ?? `API request failed (${status})`
    );
    this.status = status;
    this.payload = payload;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type RequestOptions = {
  method?: Method;
  body?: unknown;
  signal?: AbortSignal;
};

function readStoredAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const token = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
    return token && token.trim().length > 0 ? token : null;
  } catch {
    return null;
  }
}

export function setApiAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
}

function envBearerToken(): string | null {
  const token = process.env.NEXT_PUBLIC_API_BEARER_TOKEN;
  return token && token.trim().length > 0 ? token.trim() : null;
}

async function bootstrapDevAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  const bootstrapToken = process.env.NEXT_PUBLIC_K1_DEV_BOOTSTRAP_TOKEN;
  if (!bootstrapToken || bootstrapToken.trim().length === 0) {
    return null;
  }
  if (!devBootstrapPromise) {
    devBootstrapPromise = fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: bootstrapToken.trim() }),
      cache: "no-store"
    })
      .then(async (response) => {
        if (!response.ok) {
          return null;
        }
        const payload = (await response.json()) as { access_token?: string };
        const accessToken = payload.access_token?.trim();
        if (accessToken) {
          setApiAccessToken(accessToken);
          return accessToken;
        }
        return null;
      })
      .catch(() => null)
      .finally(() => {
        devBootstrapPromise = null;
      });
  }
  return devBootstrapPromise;
}

async function resolveAuthHeaderValue(): Promise<string | null> {
  const explicit = envBearerToken();
  if (explicit) {
    return `Bearer ${explicit}`;
  }
  const stored = readStoredAccessToken();
  if (stored) {
    return `Bearer ${stored}`;
  }
  const bootstrapped = await bootstrapDevAccessToken();
  if (bootstrapped) {
    return `Bearer ${bootstrapped}`;
  }
  return null;
}

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const authHeader = await resolveAuthHeaderValue();
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (authHeader) {
    headers.Authorization = authHeader;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
    cache: "no-store"
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? ((await response.json()) as ApiErrorPayload) : {};

  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }
  return payload as T;
}

export async function postJsonAllow422<T>(
  path: string,
  body?: unknown
): Promise<{ data: T; status: number }> {
  const authHeader = await resolveAuthHeaderValue();
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (authHeader) {
    headers.Authorization = authHeader;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store"
  });

  const payload = (await response.json()) as T & ApiErrorPayload;
  if (response.status === 422) {
    return { data: payload as T, status: 422 };
  }
  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }
  return { data: payload as T, status: response.status };
}

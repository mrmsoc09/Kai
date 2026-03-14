import type { ApiErrorPayload } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

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

type Method = "GET" | "POST";

type RequestOptions = {
  method?: Method;
  body?: unknown;
  signal?: AbortSignal;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json"
    },
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
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
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

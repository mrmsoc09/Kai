import { beforeEach, describe, expect, it, vi } from "vitest";

import { requestJson } from "@/lib/api/client";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function headerValue(headers: HeadersInit | undefined, name: string): string {
  if (!headers) return "";
  if (headers instanceof Headers) {
    return headers.get(name) ?? headers.get(name.toLowerCase()) ?? "";
  }
  if (Array.isArray(headers)) {
    const match = headers.find(([key]) => key.toLowerCase() === name.toLowerCase());
    return match?.[1] ?? "";
  }
  return (headers as Record<string, string>)[name] ?? (headers as Record<string, string>)[name.toLowerCase()] ?? "";
}

describe("api client auth recovery", () => {
  beforeEach(() => {
    window.localStorage.clear();
    process.env.NEXT_PUBLIC_K1_DEV_BOOTSTRAP_TOKEN = "bootstrap-token";
    process.env.NEXT_PUBLIC_API_BEARER_TOKEN = "";
  });

  it("drops an expired cached token and reboots auth on 401", async () => {
    window.localStorage.setItem("k1_access_token", "stale-token");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) {
        return jsonResponse({ access_token: "fresh-token" }, 200);
      }
      if (url.includes("/api/v1/bug-bounty/phase7/opportunity-rankings")) {
        const token = headerValue(init?.headers, "Authorization");
        if (token === "Bearer stale-token") {
          return jsonResponse({ detail: "invalid_token" }, 401);
        }
        if (token === "Bearer fresh-token") {
          return jsonResponse([{ id: "ranking-1" }], 200);
        }
      }
      return jsonResponse({ detail: "unexpected request" }, 500);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const result = await requestJson<Array<{ id: string }>>("/api/v1/bug-bounty/phase7/opportunity-rankings");

    expect(result).toEqual([{ id: "ranking-1" }]);
    expect(window.localStorage.getItem("k1_access_token")).toBe("fresh-token");
    expect(fetchMock).toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/auth/login"))).toBe(true);
  });
});

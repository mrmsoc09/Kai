import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import type { ReactNode } from "react";
import { vi } from "vitest";

declare global {
  // eslint-disable-next-line no-var
  var __NEXT_PARAMS__: Record<string, string> | undefined;
  // eslint-disable-next-line no-var
  var __NEXT_PATHNAME__: string | undefined;
}

globalThis.__NEXT_PARAMS__ = {};
globalThis.__NEXT_PATHNAME__ = "/";

vi.mock("next/navigation", () => ({
  useParams: () => globalThis.__NEXT_PARAMS__ ?? {},
  usePathname: () => globalThis.__NEXT_PATHNAME__ ?? "/",
  redirect: vi.fn()
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children)
}));

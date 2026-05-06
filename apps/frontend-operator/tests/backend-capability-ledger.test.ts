import { describe, expect, it } from "vitest";

import {
  BACKEND_CAPABILITY_LEDGER,
  BACKEND_COVERAGE_SUMMARY,
  BACKEND_MIDDLEWARE_LEDGER
} from "@/lib/backend-capability-ledger";

describe("backend capability ledger", () => {
  it("accounts for all indexed backend routers without unmapped gaps", () => {
    expect(BACKEND_CAPABILITY_LEDGER.length).toBeGreaterThan(0);
    expect(BACKEND_COVERAGE_SUMMARY.unmapped).toBe(0);
    expect(BACKEND_CAPABILITY_LEDGER.every((row) => row.status !== "UNMAPPED")).toBe(true);
  });

  it("includes middleware capability accounting", () => {
    const middlewareIds = BACKEND_MIDDLEWARE_LEDGER.map((row) => row.id);
    expect(middlewareIds).toContain("security_headers");
    expect(middlewareIds).toContain("correlation_id");
    expect(middlewareIds).toContain("csrf");
    expect(middlewareIds).toContain("rate_limit");
    expect(middlewareIds).toContain("cors");
  });
});

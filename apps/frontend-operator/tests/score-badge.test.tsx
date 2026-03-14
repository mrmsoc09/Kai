import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreBadge } from "@/components/status/ScoreBadge";

describe("ScoreBadge", () => {
  it("auto-detects percent100 values and renders percent label", () => {
    render(<ScoreBadge value={82} label="confidence" />);
    expect(screen.getByText("82.0%")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("keeps ratio values on 0-1 scale", () => {
    render(<ScoreBadge value={0.82} label="confidence" />);
    expect(screen.getByText("0.82")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders n/a for null scores", () => {
    render(<ScoreBadge value={null} label="evidence" />);
    expect(screen.getByText("n/a")).toBeInTheDocument();
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});

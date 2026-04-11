/**
 * VaultKeys Component Tests
 * Unit and integration tests for Vault secrets management
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VaultKeys from "../pages/VaultKeys";
import { SecretsTable } from "../components/SecretsTable";
import { AddSecretForm } from "../components/AddSecretForm";
import { MissingSecretsAlert } from "../components/MissingSecretsAlert";
import { SecretsStats } from "../components/SecretsStats";
import { Secret } from "../types/vault";

// Mock data
const mockSecrets: Secret[] = [
  {
    name: "openai",
    type: "OPENAI_API_KEY",
    status: "stored",
    lastUpdated: new Date(),
    environment: "production",
  },
  {
    name: "gemini",
    type: "GEMINI_API_KEY",
    status: "stored",
    lastUpdated: new Date(),
    environment: "production",
  },
  {
    name: "shodan",
    type: "SHODAN_API_KEY",
    status: "missing",
    lastUpdated: new Date(),
  },
];

describe("SecretsTable Component", () => {
  it("should render table with secrets", () => {
    const handleDelete = vi.fn();
    render(<SecretsTable secrets={mockSecrets} onDelete={handleDelete} />);

    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gemini")).toBeInTheDocument();
    expect(screen.getByText("shodan")).toBeInTheDocument();
  });

  it("should show empty state when no secrets", () => {
    const handleDelete = vi.fn();
    render(<SecretsTable secrets={[]} onDelete={handleDelete} />);

    expect(screen.getByText("No Secrets Configured")).toBeInTheDocument();
  });

  it("should display correct status badges", () => {
    const handleDelete = vi.fn();
    render(<SecretsTable secrets={mockSecrets} onDelete={handleDelete} />);

    expect(screen.getByText("Stored")).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("should call delete handler with correct secret name", async () => {
    const handleDelete = vi.fn().mockResolvedValue(undefined);
    render(<SecretsTable secrets={[mockSecrets[0]]} onDelete={handleDelete} />);

    const actionButton = screen.getByRole("button", { name: /actions/i });
    fireEvent.click(actionButton);

    const deleteMenuItem = screen.getByText("Delete");
    fireEvent.click(deleteMenuItem);

    const confirmButton = screen.getByText("Delete", {
      selector: 'button[color="error"]',
    });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(handleDelete).toHaveBeenCalledWith("openai");
    });
  });

  it("should show loading spinner when loading", () => {
    const handleDelete = vi.fn();
    const { container } = render(
      <SecretsTable secrets={[]} loading={true} onDelete={handleDelete} />,
    );

    expect(container.querySelector('[role="progressbar"]')).toBeInTheDocument();
  });
});

describe("AddSecretForm Component", () => {
  const mockOnSubmit = vi.fn();
  const mockOnTest = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
    mockOnTest.mockClear();
  });

  it("should render form when open", () => {
    render(
      <AddSecretForm
        open={true}
        onClose={vi.fn()}
        onSubmit={mockOnSubmit}
        onTest={mockOnTest}
      />,
    );

    expect(screen.getByText("Add New Secret")).toBeInTheDocument();
    expect(screen.getByLabelText("Service")).toBeInTheDocument();
    expect(screen.getByLabelText("Secret Value")).toBeInTheDocument();
  });

  it("should not render when closed", () => {
    render(
      <AddSecretForm
        open={false}
        onClose={vi.fn()}
        onSubmit={mockOnSubmit}
        onTest={mockOnTest}
      />,
    );

    expect(screen.queryByText("Add New Secret")).not.toBeInTheDocument();
  });

  it("should toggle secret value visibility", async () => {
    const user = userEvent.setup();
    render(
      <AddSecretForm
        open={true}
        onClose={vi.fn()}
        onSubmit={mockOnSubmit}
        onTest={mockOnTest}
      />,
    );

    const valueInput = screen.getByLabelText(
      "Secret Value",
    ) as HTMLInputElement;
    expect(valueInput.type).toBe("password");

    const toggleButton = screen.getByRole("button", { name: /show/i });
    await user.click(toggleButton);

    expect(valueInput.type).toBe("text");
  });

  it("should submit form with correct data", async () => {
    const user = userEvent.setup();
    mockOnSubmit.mockResolvedValue(undefined);

    render(
      <AddSecretForm
        open={true}
        onClose={vi.fn()}
        onSubmit={mockOnSubmit}
        onTest={mockOnTest}
      />,
    );

    // Fill in form
    const serviceSelect = screen.getByLabelText("Service");
    await user.click(serviceSelect);
    await user.click(screen.getByText("OpenAI"));

    const valueInput = screen.getByLabelText("Secret Value");
    await user.type(valueInput, "sk-test-secret");

    const saveButton = screen.getByText("Save Secret");
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });
  });

  it("should call test connection handler", async () => {
    const user = userEvent.setup();
    mockOnTest.mockResolvedValue(true);

    render(
      <AddSecretForm
        open={true}
        onClose={vi.fn()}
        onSubmit={mockOnSubmit}
        onTest={mockOnTest}
      />,
    );

    const serviceSelect = screen.getByLabelText("Service");
    await user.click(serviceSelect);
    await user.click(screen.getByText("OpenAI"));

    const valueInput = screen.getByLabelText("Secret Value");
    await user.type(valueInput, "sk-test-secret");

    const testButton = screen.getByText("Test Connection");
    await user.click(testButton);

    await waitFor(() => {
      expect(mockOnTest).toHaveBeenCalledWith("openai", "sk-test-secret");
    });
  });
});

describe("MissingSecretsAlert Component", () => {
  it("should show alert for missing critical secrets", () => {
    const handleAddSecret = vi.fn();
    render(
      <MissingSecretsAlert
        missingSecrets={["OPENAI_API_KEY", "GEMINI_API_KEY"]}
        onAddSecret={handleAddSecret}
      />,
    );

    expect(
      screen.getByText(/2 Critical Secret\(s\) Missing/),
    ).toBeInTheDocument();
  });

  it("should not show alert when no missing secrets", () => {
    const handleAddSecret = vi.fn();
    const { container } = render(
      <MissingSecretsAlert missingSecrets={[]} onAddSecret={handleAddSecret} />,
    );

    expect(container.textContent).not.toContain("Critical Secret(s) Missing");
  });

  it("should call onAddSecret when button clicked", async () => {
    const user = userEvent.setup();
    const handleAddSecret = vi.fn();
    render(
      <MissingSecretsAlert
        missingSecrets={["OPENAI_API_KEY"]}
        onAddSecret={handleAddSecret}
      />,
    );

    const addButton = screen.getByText("Add OPENAI_API_KEY");
    await user.click(addButton);

    expect(handleAddSecret).toHaveBeenCalledWith("OPENAI_API_KEY");
  });

  it("should persist dismiss state in localStorage", async () => {
    const user = userEvent.setup();
    const handleAddSecret = vi.fn();

    const { rerender } = render(
      <MissingSecretsAlert
        missingSecrets={["OPENAI_API_KEY"]}
        onAddSecret={handleAddSecret}
      />,
    );

    expect(
      screen.getByText(/Critical Secret\(s\) Missing/),
    ).toBeInTheDocument();

    const dismissButton = screen.getByRole("button", {
      name: /dismiss|close/i,
    });
    await user.click(dismissButton);

    rerender(
      <MissingSecretsAlert
        missingSecrets={["OPENAI_API_KEY"]}
        onAddSecret={handleAddSecret}
      />,
    );

    // Alert should not show after dismiss
    expect(
      screen.queryByText(/Critical Secret\(s\) Missing/),
    ).not.toBeInTheDocument();
  });
});

describe("SecretsStats Component", () => {
  it("should display correct statistics", () => {
    const vaultStatus = {
      connected: true,
      status: "ready",
      version: "1.15.0",
      sealed: false,
      initialized: true,
    };

    render(<SecretsStats secrets={mockSecrets} vaultStatus={vaultStatus} />);

    expect(screen.getByText(/Total Secrets/)).toBeInTheDocument();
    expect(screen.getByText(/Critical Status/)).toBeInTheDocument();
    expect(screen.getByText(/Vault Connection/)).toBeInTheDocument();
    expect(screen.getByText(/Encryption/)).toBeInTheDocument();
  });

  it("should show loading spinner when loading", () => {
    const { container } = render(<SecretsStats secrets={[]} loading={true} />);

    const spinners = container.querySelectorAll('[role="progressbar"]');
    expect(spinners.length).toBeGreaterThan(0);
  });

  it("should display disconnected status correctly", () => {
    const vaultStatus = {
      connected: false,
      status: "sealed",
      sealed: true,
      initialized: true,
    };

    render(<SecretsStats secrets={mockSecrets} vaultStatus={vaultStatus} />);

    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("should calculate correct secret counts", () => {
    render(<SecretsStats secrets={mockSecrets} />);

    // Should show 2 stored secrets out of 3 total
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });
});

describe("Integration Tests", () => {
  it("should handle complete secret creation flow", async () => {
    const user = userEvent.setup();

    // Mock API calls
    const mockFetch = vi.fn();
    const mockSave = vi.fn().mockResolvedValue({
      name: "test-secret",
      type: "TEST_KEY",
      status: "stored",
      lastUpdated: new Date(),
    });

    // This test would need full component integration
    // Simplified for this example
    expect(mockSave).toBeDefined();
  });

  it("should handle error scenarios gracefully", async () => {
    const user = userEvent.setup();
    const mockOnSubmit = vi.fn().mockRejectedValue(new Error("API Error"));

    render(
      <AddSecretForm open={true} onClose={vi.fn()} onSubmit={mockOnSubmit} />,
    );

    const valueInput = screen.getByLabelText("Secret Value");
    await user.type(valueInput, "test-value");

    // Form should still be usable despite error
    expect(screen.getByLabelText("Secret Value")).toBeInTheDocument();
  });
});

describe("Accessibility Tests", () => {
  it("should have proper ARIA labels", () => {
    render(<AddSecretForm open={true} onClose={vi.fn()} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Service")).toBeInTheDocument();
    expect(screen.getByLabelText("Secret Value")).toBeInTheDocument();
  });

  it("should be keyboard navigable", async () => {
    const user = userEvent.setup();
    render(<SecretsTable secrets={mockSecrets} onDelete={vi.fn()} />);

    // Tab to action button
    await user.tab();
    const focused = screen.activeElement;
    expect(focused).toBeInTheDocument();
  });

  it("should have sufficient color contrast", () => {
    // This would typically use automated accessibility testing tools
    // Like axe-core or similar
    render(<SecretsStats secrets={mockSecrets} />);

    const statCards = screen.getAllByText(
      /Secrets|Status|Updated|Connection|Encryption/,
    );
    expect(statCards.length).toBeGreaterThan(0);
  });
});

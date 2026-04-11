/**
 * VaultKeys Page
 * Main page for Vault secrets management
 */

import React, { useState, useEffect } from "react";
import {
  Container,
  Box,
  Typography,
  Button,
  Snackbar,
  Alert as MuiAlert,
  CircularProgress,
} from "@mui/material";
import { Plus, Lock } from "lucide-react";
import { useVaultSecrets } from "../hooks/useVaultSecrets";
import { SecretsTable } from "../components/SecretsTable";
import { AddSecretForm } from "../components/AddSecretForm";
import { MissingSecretsAlert } from "../components/MissingSecretsAlert";
import { SecretsStats } from "../components/SecretsStats";
import { AdvancedOptions } from "../components/AdvancedOptions";
import { StoreSecretRequest, ServiceType } from "../types/vault";
import { vaultClient } from "../api/vaultClient";

interface Toast {
  open: boolean;
  message: string;
  severity: "success" | "error" | "info" | "warning";
}

/**
 * VaultKeys Page Component
 */
export default function VaultKeys() {
  const [formOpen, setFormOpen] = useState(false);
  const [initialSecret, setInitialSecret] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>({
    open: false,
    message: "",
    severity: "info",
  });

  const {
    secrets,
    loading,
    error,
    vaultStatus,
    operations: {
      fetchSecrets,
      saveSecret,
      deleteSecret,
      testConnection,
      getVaultStatus,
      clearError,
    },
  } = useVaultSecrets();

  // Initial load
  useEffect(() => {
    getVaultStatus().catch(() => {
      // Vault status check failure is non-blocking
    });
  }, [getVaultStatus]);

  const handleAddSecret = () => {
    setInitialSecret(null);
    setFormOpen(true);
  };

  const handleAddMissingSecret = (secretName: string) => {
    setInitialSecret(secretName);
    setFormOpen(true);
  };

  const handleSaveSecret = async (request: StoreSecretRequest) => {
    try {
      await saveSecret(request);
      setToast({
        open: true,
        message: `Secret "${request.name}" saved successfully!`,
        severity: "success",
      });
      setFormOpen(false);
    } catch (err) {
      setToast({
        open: true,
        message: err instanceof Error ? err.message : "Failed to save secret",
        severity: "error",
      });
    }
  };

  const handleTestConnection = async (
    service: ServiceType,
    value: string,
  ): Promise<boolean> => {
    try {
      const result = await testConnection({ service, value });
      return result.success;
    } catch {
      return false;
    }
  };

  const handleDeleteSecret = async (name: string) => {
    try {
      await deleteSecret(name);
      setToast({
        open: true,
        message: `Secret "${name}" deleted successfully!`,
        severity: "success",
      });
    } catch (err) {
      setToast({
        open: true,
        message: err instanceof Error ? err.message : "Failed to delete secret",
        severity: "error",
      });
    }
  };

  const handleRefresh = async () => {
    try {
      await fetchSecrets();
      setToast({
        open: true,
        message: "Secrets refreshed successfully!",
        severity: "success",
      });
    } catch (err) {
      setToast({
        open: true,
        message: "Failed to refresh secrets",
        severity: "error",
      });
    }
  };

  const handleExportMetadata = async (): Promise<Blob> => {
    return await vaultClient.exportSecretMetadata();
  };

  const handleGetAuditLog = async () => {
    return await vaultClient.getAuditLog();
  };

  const missingSecrets = secrets
    .filter((s) => s.status === "missing")
    .map((s) => s.name);

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
          <Lock className="w-8 h-8" style={{ color: "#0284C7" }} />
          <Typography variant="h4" sx={{ fontWeight: 700, color: "#1f2937" }}>
            Vault Secrets Management
          </Typography>
        </Box>
        <Typography variant="body1" sx={{ color: "#6b7280" }}>
          Manage your API keys and sensitive credentials securely with HashiCorp
          Vault
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <MuiAlert severity="error" onClose={clearError} sx={{ mb: 3 }}>
          {error.message}
        </MuiAlert>
      )}

      {/* Missing Secrets Alert */}
      <MissingSecretsAlert
        missingSecrets={missingSecrets}
        onAddSecret={handleAddMissingSecret}
      />

      {/* Stats Cards */}
      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <SecretsStats secrets={secrets} vaultStatus={vaultStatus} />
      )}

      {/* Secrets Table Section */}
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, color: "#1f2937" }}>
            Stored Secrets
          </Typography>
          <Button
            variant="contained"
            startIcon={<Plus className="w-4 h-4" />}
            onClick={handleAddSecret}
            sx={{
              bgcolor: "#0284C7",
              "&:hover": { bgcolor: "#0369a1" },
            }}
          >
            Add Secret
          </Button>
        </Box>

        <SecretsTable
          secrets={secrets}
          loading={loading}
          onDelete={handleDeleteSecret}
          onRefresh={handleRefresh}
        />
      </Box>

      {/* Advanced Options */}
      <AdvancedOptions
        onRefresh={handleRefresh}
        onExport={handleExportMetadata}
        onGetAuditLog={handleGetAuditLog}
        onGetHealth={getVaultStatus}
      />

      {/* Add Secret Form Modal */}
      <AddSecretForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleSaveSecret}
        onTest={handleTestConnection}
      />

      {/* Toast Notifications */}
      <Snackbar
        open={toast.open}
        autoHideDuration={6000}
        onClose={() => setToast({ ...toast, open: false })}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <MuiAlert
          onClose={() => setToast({ ...toast, open: false })}
          severity={toast.severity}
          sx={{ width: "100%" }}
        >
          {toast.message}
        </MuiAlert>
      </Snackbar>
    </Container>
  );
}

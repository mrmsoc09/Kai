/**
 * useVaultSecrets Hook
 * Custom React hook for Vault secrets management
 */

import { useState, useCallback, useEffect } from "react";
import { vaultClient } from "../api/vaultClient";
import {
  Secret,
  StoreSecretRequest,
  TestSecretRequest,
  TestSecretResponse,
  VaultHealthResponse,
  VaultError,
} from "../types/vault";

interface UseVaultSecretsState {
  secrets: Secret[];
  loading: boolean;
  error: VaultError | null;
  vaultStatus: VaultHealthResponse | null;
}

/**
 * Custom hook for Vault secrets management
 * Provides methods for CRUD operations and status checking
 */
export function useVaultSecrets() {
  const [state, setState] = useState<UseVaultSecretsState>({
    secrets: [],
    loading: false,
    error: null,
    vaultStatus: null,
  });

  /**
   * Fetch all secrets from Vault
   */
  const fetchSecrets = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const secrets = await vaultClient.listSecrets();
      setState((prev) => ({
        ...prev,
        secrets,
        loading: false,
        error: null,
      }));
    } catch (error) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: error as VaultError,
      }));
      throw error;
    }
  }, []);

  /**
   * Save a new secret to Vault
   */
  const saveSecret = useCallback(
    async (request: StoreSecretRequest): Promise<Secret> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const secret = await vaultClient.storeSecret(request);
        setState((prev) => ({
          ...prev,
          secrets: [
            ...prev.secrets.filter((s) => s.name !== secret.name),
            secret,
          ],
          loading: false,
          error: null,
        }));
        return secret;
      } catch (error) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: error as VaultError,
        }));
        throw error;
      }
    },
    [],
  );

  /**
   * Delete a secret from Vault
   */
  const deleteSecret = useCallback(async (name: string) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await vaultClient.deleteSecret(name);
      setState((prev) => ({
        ...prev,
        secrets: prev.secrets.filter((s) => s.name !== name),
        loading: false,
        error: null,
      }));
    } catch (error) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: error as VaultError,
      }));
      throw error;
    }
  }, []);

  /**
   * Test connection with a service before saving
   */
  const testConnection = useCallback(
    async (request: TestSecretRequest): Promise<TestSecretResponse> => {
      try {
        const result = await vaultClient.testConnection(request);
        return result;
      } catch (error) {
        throw error as VaultError;
      }
    },
    [],
  );

  /**
   * Get Vault health status
   */
  const getVaultStatus = useCallback(async () => {
    try {
      const status = await vaultClient.getVaultStatus();
      setState((prev) => ({
        ...prev,
        vaultStatus: status,
      }));
      return status;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: error as VaultError,
      }));
      throw error;
    }
  }, []);

  /**
   * Clear any error state
   */
  const clearError = useCallback(() => {
    setState((prev) => ({
      ...prev,
      error: null,
    }));
  }, []);

  /**
   * Fetch secrets on mount
   */
  useEffect(() => {
    fetchSecrets().catch((err) => {
      console.error("Failed to fetch secrets on mount:", err);
    });
  }, [fetchSecrets]);

  return {
    ...state,
    operations: {
      fetchSecrets,
      saveSecret,
      deleteSecret,
      testConnection,
      getVaultStatus,
      clearError,
    },
  };
}

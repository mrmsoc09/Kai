/**
 * Vault Secrets Management - API Client
 * Handles all Vault-related API calls
 */

import { apiClient } from "./client";
import {
  Secret,
  SecretResponse,
  StoreSecretRequest,
  TestSecretRequest,
  TestSecretResponse,
  VaultHealthResponse,
  VaultError,
  SecretStats,
} from "../types/vault";

const BASE_PATH = "/api/vault";

/**
 * Transform API response to Secret object
 */
function transformSecretResponse(response: SecretResponse): Secret {
  return {
    name: response.name,
    type: response.type,
    status: response.status as "stored" | "missing" | "expires_soon",
    lastUpdated: new Date(response.lastUpdated),
    expiresAt: response.expiresAt ? new Date(response.expiresAt) : undefined,
    description: response.description,
    environment: response.environment as any,
  };
}

/**
 * Parse error response into VaultError
 */
function parseError(error: any): VaultError {
  if (error.response?.data) {
    return {
      code: error.response.data.code || "ERROR",
      message: error.response.data.message || error.message,
      details: error.response.data.details,
    };
  }

  return {
    code: "NETWORK_ERROR",
    message: error.message || "Network error occurred",
  };
}

/**
 * Vault API Client
 */
export const vaultClient = {
  /**
   * List all stored secrets
   */
  async listSecrets(): Promise<Secret[]> {
    try {
      const response = await apiClient.get<SecretResponse[]>(
        `${BASE_PATH}/secrets/list`,
      );
      return response.data.map(transformSecretResponse);
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Store a new secret
   */
  async storeSecret(request: StoreSecretRequest): Promise<Secret> {
    try {
      const response = await apiClient.post<SecretResponse>(
        `${BASE_PATH}/secrets/store`,
        request,
      );
      return transformSecretResponse(response.data);
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Delete a secret by name
   */
  async deleteSecret(name: string): Promise<void> {
    try {
      await apiClient.delete(
        `${BASE_PATH}/secrets/${encodeURIComponent(name)}`,
      );
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Test connection with a service
   */
  async testConnection(
    request: TestSecretRequest,
  ): Promise<TestSecretResponse> {
    try {
      const response = await apiClient.post<TestSecretResponse>(
        `${BASE_PATH}/secrets/test`,
        request,
      );
      return response.data;
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Get Vault health status
   */
  async getVaultStatus(): Promise<VaultHealthResponse> {
    try {
      const response = await apiClient.get<VaultHealthResponse>(
        `${BASE_PATH}/health`,
      );
      return response.data;
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Get secret statistics
   */
  async getSecretStats(): Promise<SecretStats> {
    try {
      const response = await apiClient.get<SecretStats>(
        `${BASE_PATH}/secrets/stats`,
      );
      return response.data;
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Export secrets metadata (no actual secret values)
   */
  async exportSecretMetadata(): Promise<Blob> {
    try {
      const response = await apiClient.get(`${BASE_PATH}/secrets/export`, {
        responseType: "blob",
      });
      return response.data;
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Get audit log for secret operations
   */
  async getAuditLog(limit: number = 50): Promise<
    Array<{
      timestamp: string;
      action: string;
      secret: string;
      user?: string;
    }>
  > {
    try {
      const response = await apiClient.get(`${BASE_PATH}/secrets/audit`, {
        params: { limit },
      });
      return response.data;
    } catch (error) {
      throw parseError(error);
    }
  },

  /**
   * Validate secret format for a service type
   */
  async validateSecret(service: string, value: string): Promise<boolean> {
    try {
      const response = await apiClient.post<{ valid: boolean }>(
        `${BASE_PATH}/secrets/validate`,
        { service, value },
      );
      return response.data.valid;
    } catch (error) {
      throw parseError(error);
    }
  },
};

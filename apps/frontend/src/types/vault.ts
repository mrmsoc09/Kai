/**
 * Vault Secrets Management - TypeScript Types
 * Type definitions for Vault API and UI components
 */

export type ServiceType =
  | "openai"
  | "gemini"
  | "ollama"
  | "shodan"
  | "github"
  | "aws"
  | "custom";

export type SecretStatus = "stored" | "missing" | "expires_soon";

export type EnvironmentTag = "production" | "staging" | "development";

/**
 * Secret record from Vault
 */
export interface Secret {
  name: string;
  type: string;
  status: SecretStatus;
  lastUpdated: Date;
  expiresAt?: Date;
  description?: string;
  environment?: EnvironmentTag;
}

/**
 * Secret response from API
 */
export interface SecretResponse {
  name: string;
  type: string;
  status: string;
  lastUpdated: string;
  expiresAt?: string;
  description?: string;
  environment?: string;
}

/**
 * Request to store a new secret
 */
export interface StoreSecretRequest {
  name: string;
  type: string;
  value: string;
  description?: string;
  tags?: string[];
  environment?: EnvironmentTag;
}

/**
 * Request to test a secret connection
 */
export interface TestSecretRequest {
  service: ServiceType;
  value: string;
}

/**
 * Response from testing a secret
 */
export interface TestSecretResponse {
  success: boolean;
  message: string;
  apiVersion?: string;
}

/**
 * Vault health/status response
 */
export interface VaultHealthResponse {
  connected: boolean;
  status: string;
  version?: string;
  sealed?: boolean;
  initialized?: boolean;
}

/**
 * Secret statistics
 */
export interface SecretStats {
  totalSecrets: number;
  storedSecrets: number;
  missingSecrets: string[];
  expiringCount: number;
  lastUpdated: string;
}

/**
 * API error response
 */
export interface VaultError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Service type configuration
 */
export interface ServiceConfig {
  name: ServiceType;
  displayName: string;
  icon: string;
  defaultType: string;
}

/**
 * Hook return type for useVaultSecrets
 */
export interface UseVaultSecretsReturn {
  secrets: Secret[];
  loading: boolean;
  error: VaultError | null;
  operations: {
    fetchSecrets: () => Promise<void>;
    saveSecret: (req: StoreSecretRequest) => Promise<Secret>;
    deleteSecret: (name: string) => Promise<void>;
    testConnection: (req: TestSecretRequest) => Promise<TestSecretResponse>;
    getVaultStatus: () => Promise<VaultHealthResponse>;
    clearError: () => void;
  };
}

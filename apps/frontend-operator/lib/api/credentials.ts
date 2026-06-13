/**
 * credentials.ts — API client for /api/v1/credentials/*
 *
 * Write-only credential pattern: GET endpoints return metadata only.
 * Plaintext secrets are never sent back from the API.
 */
import { requestJson } from "./client";

// ============================================================================
// Types (mirror of backend credential_schemas.py)
// ============================================================================

export type CredentialStatus = "active" | "expired" | "invalid" | "needs_renewal";

export type CredentialResponse = {
  id: string;
  program_id: string;
  access_type: string;
  status: CredentialStatus;
  credential_username: string | null;
  last_validated: string | null;
  validation_method: string | null;
  created_at: string;
  updated_at: string;
  notes: string | null;
  access_count: number;
  last_accessed_at: string | null;
  last_accessed_by: string | null;
};

export type ListCredentialsResponse = {
  program_id: string;
  credentials: CredentialResponse[];
};

export type AccessMetadataResponse = {
  id: string;
  program_id: string;
  access_type: string;
  enabled: boolean;
  signup_url: string | null;
  signup_instructions: string | null;
  requires_email: boolean;
  requires_payment: boolean;
  rate_limits: string | null;
  available_endpoints: string | null;
  testing_account_available: boolean;
  testing_account_url: string | null;
  testing_instructions: string | null;
  created_at: string;
  updated_at: string;
};

export type AccessMetadataListResponse = {
  program_id: string;
  metadata: AccessMetadataResponse[];
};

export type HunterAccountRecord = {
  source_index: number;
  slug: string;
  display_name: string;
  platform_hint: string | null;
  credential_kind: string;
  username: string | null;
  email: string | null;
  source_url: string | null;
  vault_path: string;
  has_password: boolean;
  has_totp: boolean;
  has_backup_codes: boolean;
};

export type HunterAccountInventoryResponse = {
  source_path: string;
  record_count: number;
  counts: Record<string, number>;
  records: HunterAccountRecord[];
};

export type ScanSuggestionRecord = {
  opportunity_id: string;
  name: string;
  organization: string;
  platform: string;
  score: number;
  reasons: string[];
  matching_accounts: string[];
};

export type ScanSuggestionListResponse = {
  items: ScanSuggestionRecord[];
};

export type ValidateCredentialResponse = {
  valid: boolean;
  reason: string;
  tested_at: string | null;
};

export type StoreCredentialBody = {
  access_type: string;
  credentials: Record<string, string>;
  username?: string | null;
  notes?: string | null;
};

export type UpsertAccessMetadataBody = {
  access_type: string;
  enabled?: boolean;
  signup_url?: string | null;
  signup_instructions?: string | null;
  requires_email?: boolean;
  requires_payment?: boolean;
  rate_limits?: string | null;
  available_endpoints?: string | null;
  testing_account_available?: boolean;
  testing_account_url?: string | null;
  testing_instructions?: string | null;
};

// ============================================================================
// API Functions
// ============================================================================

/** List all credentials for a program (metadata only — no plaintext). */
export function listCredentials(programId: string, signal?: AbortSignal) {
  return requestJson<ListCredentialsResponse>(
    `/api/v1/credentials/${programId}`,
    { signal }
  );
}

/** Store (create) a new credential in Vault. Returns metadata. */
export function storeCredential(
  programId: string,
  accessType: string,
  body: StoreCredentialBody,
  signal?: AbortSignal
) {
  return requestJson<CredentialResponse>(
    `/api/v1/credentials/${programId}/${accessType}`,
    { method: "POST", body, signal }
  );
}

/** Update an existing credential in Vault. Returns updated metadata. */
export function updateCredential(
  programId: string,
  accessType: string,
  body: StoreCredentialBody,
  signal?: AbortSignal
) {
  return requestJson<CredentialResponse>(
    `/api/v1/credentials/${programId}/${accessType}`,
    { method: "PUT", body, signal }
  );
}

/** Delete a credential from Vault and DB. */
export function deleteCredential(programId: string, accessType: string) {
  return requestJson<{ ok: boolean; message: string }>(
    `/api/v1/credentials/${programId}/${accessType}`,
    { method: "DELETE" }
  );
}

/** Trigger live validation of a stored credential. */
export function validateCredential(programId: string, accessType: string) {
  return requestJson<ValidateCredentialResponse>(
    `/api/v1/credentials/${programId}/${accessType}/validate`,
    { method: "POST", body: {} }
  );
}

/** List all access metadata for a program. */
export function getAccessMetadata(programId: string, signal?: AbortSignal) {
  return requestJson<AccessMetadataListResponse>(
    `/api/v1/credentials/access-metadata/${programId}`,
    { signal }
  );
}

/** Create or update access metadata (signup URL, instructions, etc.). */
export function upsertAccessMetadata(
  programId: string,
  accessType: string,
  body: UpsertAccessMetadataBody
) {
  return requestJson<AccessMetadataResponse>(
    `/api/v1/credentials/access-metadata/${programId}/${accessType}`,
    { method: "PUT", body }
  );
}

/** Load the imported hunter-account inventory derived from the Proton CSV. */
export function getHunterAccountInventory(signal?: AbortSignal) {
  return requestJson<HunterAccountInventoryResponse>(
    "/api/v1/credentials/hunter-accounts",
    { signal }
  );
}

/** Load scan suggestions that are informed by the imported hunter accounts. */
export function getScanSuggestions(limit = 50, signal?: AbortSignal) {
  return requestJson<ScanSuggestionListResponse>(
    `/api/v1/credentials/scan-suggestions?limit=${encodeURIComponent(String(limit))}`,
    { signal }
  );
}

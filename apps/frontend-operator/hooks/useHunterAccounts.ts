"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteCredential,
  getAccessMetadata,
  listCredentials,
  storeCredential,
  updateCredential,
  upsertAccessMetadata,
  validateCredential,
} from "@/lib/api/credentials";
import type {
  AccessMetadataResponse,
  CredentialResponse,
  StoreCredentialBody,
  UpsertAccessMetadataBody,
} from "@/lib/api/credentials";
import { queryKeys } from "@/lib/query-keys";

export type { AccessMetadataResponse, CredentialResponse };

export const HUNTER_ACCESS_TYPE = "hunter_account";

/**
 * useCredentialsForProgram — all data + mutations needed for a single program's
 * hunter account management. Returns write-only metadata (no plaintext secrets).
 */
export function useCredentialsForProgram(programId: string | null) {
  const queryClient = useQueryClient();

  // ── Queries ────────────────────────────────────────────────────────────────

  /** Credential metadata (status, username, last_validated — no secrets). */
  const credentialsQuery = useQuery({
    queryKey: queryKeys.credentials.forProgram(programId ?? "__none__"),
    queryFn: ({ signal }) => listCredentials(programId!, signal),
    enabled: !!programId,
    staleTime: 30_000,
  });

  /** Access metadata: signup URL, instructions, testing info. */
  const metadataQuery = useQuery({
    queryKey: queryKeys.credentials.metadata(programId ?? "__none__"),
    queryFn: ({ signal }) => getAccessMetadata(programId!, signal),
    enabled: !!programId,
    staleTime: 60_000,
  });

  // ── Derived: hunter_account credential ────────────────────────────────────

  const hunterCredential: CredentialResponse | null =
    credentialsQuery.data?.credentials.find(
      (c) => c.access_type === HUNTER_ACCESS_TYPE
    ) ?? null;

  const hunterMetadata: AccessMetadataResponse | null =
    metadataQuery.data?.metadata.find(
      (m) => m.access_type === HUNTER_ACCESS_TYPE
    ) ?? null;

  const isConfigured = hunterCredential !== null && hunterCredential.status !== "invalid";

  // ── Mutations ──────────────────────────────────────────────────────────────

  /** Save (create or update) credentials to Vault. Automatically upserts. */
  const saveMutation = useMutation({
    mutationFn: (body: Omit<StoreCredentialBody, "access_type">) => {
      const payload: StoreCredentialBody = { ...body, access_type: HUNTER_ACCESS_TYPE };
      if (hunterCredential) {
        return updateCredential(programId!, HUNTER_ACCESS_TYPE, payload);
      }
      return storeCredential(programId!, HUNTER_ACCESS_TYPE, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.credentials.forProgram(programId!),
      });
    },
  });

  /** Delete credentials from Vault. */
  const deleteMutation = useMutation({
    mutationFn: () => deleteCredential(programId!, HUNTER_ACCESS_TYPE),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.credentials.forProgram(programId!),
      });
    },
  });

  /** Validate stored credentials against the live service. */
  const validateMutation = useMutation({
    mutationFn: () => validateCredential(programId!, HUNTER_ACCESS_TYPE),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.credentials.forProgram(programId!),
      });
    },
  });

  /** Create or update access metadata (signup URL, instructions). */
  const upsertMetadataMutation = useMutation({
    mutationFn: (body: Omit<UpsertAccessMetadataBody, "access_type">) =>
      upsertAccessMetadata(programId!, HUNTER_ACCESS_TYPE, {
        ...body,
        access_type: HUNTER_ACCESS_TYPE,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.credentials.metadata(programId!),
      });
    },
  });

  return {
    // Queries
    credentialsQuery,
    metadataQuery,
    // Derived
    hunterCredential,
    hunterMetadata,
    isConfigured,
    // Mutations
    saveMutation,
    deleteMutation,
    validateMutation,
    upsertMetadataMutation,
  };
}

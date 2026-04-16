/**
 * Operator identity constants for audit-trail actor fields.
 *
 * All strings follow the platform-wide convention: "operator.console.{surface}".
 *
 * These are fallback identifiers used when no authenticated user identity is
 * available from a session context. Once an /auth/me response (or equivalent)
 * is stored in a React context or Zustand store, replace the usages of these
 * constants with the real username/email from that source.
 *
 * Search for APPROVAL_CONSOLE_ACTOR to find every place that needs updating
 * once real identity is plumbed.
 */

/** Actor string written to `decided_by` on all approval gate decisions. */
export const APPROVAL_CONSOLE_ACTOR = "operator.console.approvals" as const;

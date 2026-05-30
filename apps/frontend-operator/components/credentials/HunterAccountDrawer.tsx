"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import type { ProgramOpportunity } from "@/lib/types/bug-bounty";
import { useCredentialsForProgram } from "@/hooks/useHunterAccounts";

// ============================================================================
// Colour palette (matrix green)
// ============================================================================
const C = {
  bg: "#0a0f0a",
  panel: "#0d140d",
  border: "#003300",
  borderActive: "#006600",
  green: "#00FF41",
  greenDim: "#007A1E",
  greenFaint: "rgba(0,255,65,0.07)",
  greenGlow: "rgba(0,255,65,0.35)",
  red: "#ff4444",
  redDim: "#883333",
  orange: "#ff9900",
  text: "#00e536",
  muted: "#004d10",
  overlay: "rgba(0,0,0,0.72)",
  inputBg: "#060c06",
} as const;

// ============================================================================
// SecretInput — text input with show/hide toggle
// ============================================================================
function SecretInput({
  value,
  onChange,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
      <input
        type={revealed ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "••••••••••"}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        style={{
          flex: 1,
          background: C.inputBg,
          border: `1px solid ${C.border}`,
          borderRadius: 3,
          color: C.green,
          fontFamily: "IBM Plex Mono, monospace",
          fontSize: "0.75rem",
          padding: "5px 32px 5px 8px",
          outline: "none",
          opacity: disabled ? 0.4 : 1,
        }}
      />
      <button
        type="button"
        onClick={() => setRevealed((r) => !r)}
        disabled={disabled}
        title={revealed ? "Hide" : "Reveal"}
        style={{
          position: "absolute",
          right: 6,
          background: "none",
          border: "none",
          cursor: disabled ? "default" : "pointer",
          color: C.greenDim,
          fontSize: "0.7rem",
          padding: 0,
          lineHeight: 1,
        }}
      >
        {revealed ? "⊘" : "⊙"}
      </button>
    </div>
  );
}

// ============================================================================
// PlainInput — non-secret text input
// ============================================================================
function PlainInput({
  value,
  onChange,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      autoComplete="off"
      spellCheck={false}
      style={{
        width: "100%",
        background: C.inputBg,
        border: `1px solid ${C.border}`,
        borderRadius: 3,
        color: C.green,
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: "0.75rem",
        padding: "5px 8px",
        outline: "none",
        boxSizing: "border-box",
        opacity: disabled ? 0.4 : 1,
      }}
    />
  );
}

// ============================================================================
// SecretTextarea — multiline secret input with toggle
// ============================================================================
function SecretTextarea({
  value,
  onChange,
  placeholder,
  rows,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div style={{ position: "relative" }}>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows ?? 3}
        autoComplete="off"
        spellCheck={false}
        style={{
          width: "100%",
          background: C.inputBg,
          border: `1px solid ${C.border}`,
          borderRadius: 3,
          color: revealed ? C.green : C.greenDim,
          fontFamily: "IBM Plex Mono, monospace",
          fontSize: "0.72rem",
          padding: "5px 32px 5px 8px",
          outline: "none",
          resize: "vertical",
          boxSizing: "border-box",
          filter: revealed ? "none" : "blur(3px)",
          opacity: disabled ? 0.4 : 1,
          transition: "filter 0.15s ease",
        }}
      />
      <button
        type="button"
        onClick={() => setRevealed((r) => !r)}
        disabled={disabled}
        title={revealed ? "Hide" : "Reveal"}
        style={{
          position: "absolute",
          top: 6,
          right: 6,
          background: "none",
          border: "none",
          cursor: disabled ? "default" : "pointer",
          color: C.greenDim,
          fontSize: "0.7rem",
          padding: 0,
          lineHeight: 1,
        }}
      >
        {revealed ? "⊘" : "⊙"}
      </button>
    </div>
  );
}

// ============================================================================
// PlainTextarea
// ============================================================================
function PlainTextarea({
  value,
  onChange,
  placeholder,
  rows,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      rows={rows ?? 3}
      spellCheck={false}
      style={{
        width: "100%",
        background: C.inputBg,
        border: `1px solid ${C.border}`,
        borderRadius: 3,
        color: C.green,
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: "0.72rem",
        padding: "5px 8px",
        outline: "none",
        resize: "vertical",
        boxSizing: "border-box",
        opacity: disabled ? 0.4 : 1,
      }}
    />
  );
}

// ============================================================================
// Section heading
// ============================================================================
function SectionLabel({ label }: { label: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginTop: "1rem",
        marginBottom: "0.4rem",
      }}
    >
      <div style={{ flex: 1, height: 1, background: C.border }} />
      <span
        style={{
          fontSize: "0.58rem",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          color: C.greenDim,
          fontFamily: "IBM Plex Mono, monospace",
        }}
      >
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  );
}

// ============================================================================
// FieldRow — label + input pair
// ============================================================================
function FieldRow({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div style={{ marginBottom: "0.55rem" }}>
      <div
        style={{
          fontSize: "0.62rem",
          color: C.greenDim,
          letterSpacing: "0.08em",
          marginBottom: "3px",
          fontFamily: "IBM Plex Mono, monospace",
        }}
      >
        {label}
        {hint && (
          <span style={{ color: C.muted, marginLeft: 6 }}>— {hint}</span>
        )}
      </div>
      {children}
    </div>
  );
}

// ============================================================================
// SecurityQuestionPair
// ============================================================================
function SecurityQuestionPair({
  index,
  question,
  answer,
  onQuestion,
  onAnswer,
  disabled,
}: {
  index: number;
  question: string;
  answer: string;
  onQuestion: (v: string) => void;
  onAnswer: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div style={{ marginBottom: "0.6rem" }}>
      <div
        style={{
          fontSize: "0.58rem",
          color: C.muted,
          letterSpacing: "0.08em",
          marginBottom: "3px",
          fontFamily: "IBM Plex Mono, monospace",
        }}
      >
        SECURITY QUESTION {index}
      </div>
      <PlainInput
        value={question}
        onChange={onQuestion}
        placeholder={`e.g. "What was your first pet's name?"`}
        disabled={disabled}
      />
      <div style={{ marginTop: 3 }}>
        <SecretInput
          value={answer}
          onChange={onAnswer}
          placeholder="Answer ••••••"
          disabled={disabled}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Form state
// ============================================================================
type FormState = {
  // Identity (visible)
  username: string;
  email: string;
  display_name: string;
  // Authentication (secret)
  password: string;
  pin: string;
  mnemonic_passphrase: string;
  // 2FA & Recovery (secret)
  totp_secret: string;
  backup_codes: string;
  security_question_1: string;
  security_answer_1: string;
  security_question_2: string;
  security_answer_2: string;
  security_question_3: string;
  security_answer_3: string;
  // API Access (secret)
  api_key: string;
  pat_token: string;
  oauth_client_id: string;
  oauth_client_secret: string;
  bearer_token: string;
  session_cookie: string;
  // Notes (visible, stored in DB not Vault)
  notes: string;
  additional: string;
  // Access metadata
  signup_url: string;
  signup_instructions: string;
  testing_account_available: boolean;
  testing_account_url: string;
  testing_instructions: string;
};

const EMPTY_FORM: FormState = {
  username: "",
  email: "",
  display_name: "",
  password: "",
  pin: "",
  mnemonic_passphrase: "",
  totp_secret: "",
  backup_codes: "",
  security_question_1: "",
  security_answer_1: "",
  security_question_2: "",
  security_answer_2: "",
  security_question_3: "",
  security_answer_3: "",
  api_key: "",
  pat_token: "",
  oauth_client_id: "",
  oauth_client_secret: "",
  bearer_token: "",
  session_cookie: "",
  notes: "",
  additional: "",
  signup_url: "",
  signup_instructions: "",
  testing_account_available: false,
  testing_account_url: "",
  testing_instructions: "",
};

type FormAction = { field: keyof FormState; value: string | boolean };

function formReducer(state: FormState, action: FormAction): FormState {
  return { ...state, [action.field]: action.value };
}

// ============================================================================
// StatusBadge
// ============================================================================
function StatusBadge({ configured, status }: { configured: boolean; status?: string }) {
  const color = configured ? C.green : C.orange;
  const text = configured ? `✓ CONFIGURED (${status ?? "active"})` : "○ NOT CONFIGURED";
  return (
    <span
      style={{
        fontSize: "0.62rem",
        fontFamily: "IBM Plex Mono, monospace",
        color,
        border: `1px solid ${color}`,
        borderRadius: 2,
        padding: "2px 6px",
        letterSpacing: "0.08em",
        textShadow: configured ? `0 0 6px ${C.greenGlow}` : "none",
      }}
    >
      {text}
    </span>
  );
}

// ============================================================================
// ActionButton
// ============================================================================
function ActionButton({
  onClick,
  children,
  variant = "primary",
  disabled,
  loading,
}: {
  onClick: () => void;
  children: React.ReactNode;
  variant?: "primary" | "danger" | "ghost" | "warn";
  disabled?: boolean;
  loading?: boolean;
}) {
  const colors = {
    primary: { bg: "rgba(0,255,65,0.1)", border: C.borderActive, color: C.green },
    danger: { bg: "rgba(255,68,68,0.1)", border: C.redDim, color: C.red },
    ghost: { bg: "rgba(0,0,0,0.3)", border: C.border, color: C.greenDim },
    warn: { bg: "rgba(255,153,0,0.1)", border: "#664400", color: C.orange },
  };
  const s = colors[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        background: s.bg,
        border: `1px solid ${s.border}`,
        borderRadius: 3,
        color: s.color,
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: "0.68rem",
        letterSpacing: "0.06em",
        padding: "5px 12px",
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.5 : 1,
        transition: "all 0.1s ease",
        whiteSpace: "nowrap",
      }}
    >
      {loading ? "⟳ working..." : children}
    </button>
  );
}

// ============================================================================
// HunterAccountDrawer
// ============================================================================

type Props = {
  program: ProgramOpportunity | null;
  open: boolean;
  onClose: () => void;
};

export function HunterAccountDrawer({ program, open, onClose }: Props) {
  const [form, dispatch] = useReducer(formReducer, EMPTY_FORM);
  const [toast, setToast] = useState<{ message: string; ok: boolean } | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  const {
    credentialsQuery,
    metadataQuery,
    hunterCredential,
    hunterMetadata,
    isConfigured,
    saveMutation,
    deleteMutation,
    validateMutation,
    upsertMetadataMutation,
  } = useCredentialsForProgram(program?.id ?? null);

  // ── Sync metadata into form fields when it loads ──────────────────────────
  useEffect(() => {
    if (hunterMetadata) {
      dispatch({ field: "signup_url", value: hunterMetadata.signup_url ?? "" });
      dispatch({ field: "signup_instructions", value: hunterMetadata.signup_instructions ?? "" });
      dispatch({ field: "testing_account_available", value: hunterMetadata.testing_account_available });
      dispatch({ field: "testing_account_url", value: hunterMetadata.testing_account_url ?? "" });
      dispatch({ field: "testing_instructions", value: hunterMetadata.testing_instructions ?? "" });
    }
  }, [hunterMetadata]);

  // ── Sync credential metadata (non-secret username, notes) ─────────────────
  useEffect(() => {
    if (hunterCredential) {
      dispatch({ field: "username", value: hunterCredential.credential_username ?? "" });
      dispatch({ field: "notes", value: hunterCredential.notes ?? "" });
    }
  }, [hunterCredential]);

  // ── Reset secret fields every time the drawer opens (write-only) ──────────
  useEffect(() => {
    if (open) {
      const secretFields: Array<keyof FormState> = [
        "password", "pin", "mnemonic_passphrase",
        "totp_secret", "backup_codes",
        "security_answer_1", "security_answer_2", "security_answer_3",
        "api_key", "pat_token", "oauth_client_secret",
        "bearer_token", "session_cookie",
      ];
      for (const f of secretFields) {
        dispatch({ field: f, value: "" });
      }
    }
  }, [open, program?.id]);

  // ── Close on Escape ───────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // ── Toast helper ──────────────────────────────────────────────────────────
  const showToast = (message: string, ok: boolean) => {
    setToast({ message, ok });
    setTimeout(() => setToast(null), 4000);
  };

  // ── Set form field ─────────────────────────────────────────────────────────
  const set = (field: keyof FormState) => (value: string | boolean) =>
    dispatch({ field, value });

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleSaveMetadata = () => {
    if (!program) return;
    upsertMetadataMutation.mutate(
      {
        signup_url: form.signup_url || null,
        signup_instructions: form.signup_instructions || null,
        testing_account_available: form.testing_account_available,
        testing_account_url: form.testing_account_url || null,
        testing_instructions: form.testing_instructions || null,
        enabled: true,
      },
      {
        onSuccess: () => showToast("Access metadata saved.", true),
        onError: (e) => showToast(`Failed: ${(e as Error).message}`, false),
      }
    );
  };

  const handleSaveCredentials = () => {
    if (!program) return;

    // Build the credential dict — only include non-empty secret fields
    const credentials: Record<string, string> = {};
    const secretFields = {
      email: form.email,
      display_name: form.display_name,
      password: form.password,
      pin: form.pin,
      mnemonic_passphrase: form.mnemonic_passphrase,
      totp_secret: form.totp_secret,
      backup_codes: form.backup_codes,
      security_question_1: form.security_question_1,
      security_answer_1: form.security_answer_1,
      security_question_2: form.security_question_2,
      security_answer_2: form.security_answer_2,
      security_question_3: form.security_question_3,
      security_answer_3: form.security_answer_3,
      api_key: form.api_key,
      pat_token: form.pat_token,
      oauth_client_id: form.oauth_client_id,
      oauth_client_secret: form.oauth_client_secret,
      bearer_token: form.bearer_token,
      session_cookie: form.session_cookie,
      additional: form.additional,
    };
    for (const [k, v] of Object.entries(secretFields)) {
      if (v.trim()) credentials[k] = v.trim();
    }

    if (Object.keys(credentials).length === 0 && !form.username && !form.notes) {
      showToast("Nothing to save — fill at least one field.", false);
      return;
    }

    saveMutation.mutate(
      {
        credentials,
        username: form.username || null,
        notes: form.notes || null,
      },
      {
        onSuccess: () => showToast("Credentials saved to Vault ✓", true),
        onError: (e) => showToast(`Save failed: ${(e as Error).message}`, false),
      }
    );
  };

  const handleValidate = () => {
    validateMutation.mutate(undefined, {
      onSuccess: (result) => {
        showToast(
          result.valid ? `Validation passed: ${result.reason}` : `Validation failed: ${result.reason}`,
          result.valid
        );
      },
      onError: (e) => showToast(`Validate error: ${(e as Error).message}`, false),
    });
  };

  const handleDelete = () => {
    if (!window.confirm(`Delete all hunter credentials for "${program?.name}"? This cannot be undone.`)) return;
    deleteMutation.mutate(undefined, {
      onSuccess: () => {
        showToast("Credentials deleted.", true);
        // Clear the form
        for (const f of Object.keys(EMPTY_FORM) as Array<keyof FormState>) {
          dispatch({ field: f, value: typeof EMPTY_FORM[f] === "boolean" ? false : "" });
        }
      },
      onError: (e) => showToast(`Delete failed: ${(e as Error).message}`, false),
    });
  };

  // ── Section toggle helper ─────────────────────────────────────────────────
  const toggleSection = (s: string) =>
    setActiveSection((prev) => (prev === s ? null : s));
  const isOpen = (s: string) => activeSection === null || activeSection === s;

  // ── Render ────────────────────────────────────────────────────────────────
  if (!open) return null;

  const busy = saveMutation.isPending || deleteMutation.isPending || validateMutation.isPending;

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: C.overlay,
          zIndex: 1000,
        }}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(640px, 92vw)",
          background: C.panel,
          borderLeft: `1px solid ${C.border}`,
          zIndex: 1001,
          display: "flex",
          flexDirection: "column",
          fontFamily: "IBM Plex Mono, monospace",
          overflowY: "hidden",
          boxShadow: `-8px 0 32px rgba(0,255,65,0.05)`,
        }}
      >
        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div
          style={{
            padding: "12px 16px",
            borderBottom: `1px solid ${C.border}`,
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexShrink: 0,
          }}
        >
          <span style={{ color: C.greenDim, fontSize: "0.9rem" }}>⚿</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: C.green, fontSize: "0.8rem", fontWeight: 600, letterSpacing: "0.04em" }}>
              HUNTER ACCOUNT
            </div>
            <div
              style={{
                color: C.text,
                fontSize: "0.72rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {program?.name ?? "—"}
              {program?.platform && (
                <span style={{ color: C.greenDim, marginLeft: 8 }}>
                  [{program.platform.toUpperCase()}]
                </span>
              )}
            </div>
          </div>

          {/* Credential status */}
          <StatusBadge configured={isConfigured} status={hunterCredential?.status} />

          {/* Close */}
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: C.greenDim,
              cursor: "pointer",
              fontSize: "1rem",
              padding: 4,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* ── Scrollable body ──────────────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "0 16px",
            paddingBottom: 100,
          }}
        >

          {/* Loading skeleton */}
          {(credentialsQuery.isLoading || metadataQuery.isLoading) && (
            <div style={{ color: C.muted, fontSize: "0.68rem", padding: "12px 0" }}>
              ⟳ Loading account data...
            </div>
          )}

          {/* ── ACCESS SETUP ──────────────────────────────────────────────── */}
          <CollapsibleSection
            id="access-setup"
            title="ACCESS SETUP"
            subtitle="Signup URL and instructions for this program"
            active={activeSection}
            toggle={toggleSection}
          >
            <FieldRow label="Program Policy URL" hint="from program listing">
              <a
                href={program?.policy_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: C.green,
                  fontSize: "0.72rem",
                  textDecoration: "underline",
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {program?.policy_url ?? "No policy URL on record"}
              </a>
            </FieldRow>

            <FieldRow label="Signup / Registration URL">
              <PlainInput
                value={form.signup_url}
                onChange={set("signup_url")}
                placeholder="https://hackerone.com/programs/..."
                disabled={busy}
              />
            </FieldRow>

            <FieldRow label="Account Creation Instructions" hint="shown before scanning">
              <PlainTextarea
                value={form.signup_instructions}
                onChange={set("signup_instructions")}
                placeholder={"1. Visit signup_url above\n2. Create account with hunter email\n3. Complete email verification\n4. Apply to program's bug bounty scope\n5. Save credentials below"}
                rows={5}
                disabled={busy}
              />
            </FieldRow>

            <FieldRow label="Testing Account Available">
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  color: C.greenDim,
                  fontSize: "0.72rem",
                }}
              >
                <input
                  type="checkbox"
                  checked={form.testing_account_available}
                  onChange={(e) => set("testing_account_available")(e.target.checked)}
                  style={{ accentColor: C.green }}
                  disabled={busy}
                />
                Program provides a dedicated testing / sandbox account
              </label>
            </FieldRow>

            {form.testing_account_available && (
              <>
                <FieldRow label="Testing Account URL">
                  <PlainInput
                    value={form.testing_account_url}
                    onChange={set("testing_account_url")}
                    placeholder="https://..."
                    disabled={busy}
                  />
                </FieldRow>
                <FieldRow label="Testing Account Instructions">
                  <PlainTextarea
                    value={form.testing_instructions}
                    onChange={set("testing_instructions")}
                    placeholder="How to get the testing account..."
                    rows={3}
                    disabled={busy}
                  />
                </FieldRow>
              </>
            )}

            <div style={{ marginTop: 8 }}>
              <ActionButton
                onClick={handleSaveMetadata}
                loading={upsertMetadataMutation.isPending}
                disabled={busy}
              >
                ⊕ Save Access Metadata
              </ActionButton>
            </div>
          </CollapsibleSection>

          {/* ── IDENTITY ─────────────────────────────────────────────────── */}
          <CollapsibleSection
            id="identity"
            title="IDENTITY"
            subtitle="Username and display info (visible in status)"
            active={activeSection}
            toggle={toggleSection}
          >
            <FieldRow label="Username / Handle" hint="shown in status badge">
              <PlainInput
                value={form.username}
                onChange={set("username")}
                placeholder="hunter_handle"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Email Address" hint="stored in Vault">
              <PlainInput
                value={form.email}
                onChange={set("email")}
                placeholder="hunter@email.com"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Display Name / Alias" hint="stored in Vault">
              <PlainInput
                value={form.display_name}
                onChange={set("display_name")}
                placeholder="H4ck3r Name"
                disabled={busy}
              />
            </FieldRow>
          </CollapsibleSection>

          {/* ── AUTHENTICATION ──────────────────────────────────────────── */}
          <CollapsibleSection
            id="authentication"
            title="AUTHENTICATION"
            subtitle="Password, PIN, and passphrase — always write-only"
            active={activeSection}
            toggle={toggleSection}
          >
            <div
              style={{
                background: "rgba(255,153,0,0.05)",
                border: "1px solid rgba(255,153,0,0.2)",
                borderRadius: 3,
                padding: "5px 8px",
                marginBottom: 10,
                fontSize: "0.62rem",
                color: C.orange,
                letterSpacing: "0.04em",
              }}
            >
              ⚠ Fields are WRITE-ONLY. Existing values are never retrieved. Saving empty fields will NOT clear Vault — only filled fields are written.
            </div>

            <FieldRow label="Password" hint="main account password">
              <SecretInput
                value={form.password}
                onChange={set("password")}
                placeholder="Enter new password to overwrite"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="PIN Code" hint="numeric PIN if required">
              <SecretInput
                value={form.pin}
                onChange={set("pin")}
                placeholder="e.g. 1234"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Mnemonic Passphrase" hint="BIP-39 / wallet recovery phrase">
              <SecretTextarea
                value={form.mnemonic_passphrase}
                onChange={set("mnemonic_passphrase")}
                placeholder="word1 word2 word3 ... word24"
                rows={3}
                disabled={busy}
              />
            </FieldRow>
          </CollapsibleSection>

          {/* ── 2FA & RECOVERY ──────────────────────────────────────────── */}
          <CollapsibleSection
            id="2fa"
            title="2FA & RECOVERY"
            subtitle="TOTP secrets, backup codes, security questions"
            active={activeSection}
            toggle={toggleSection}
          >
            <FieldRow label="TOTP Secret (Base32)" hint="scan QR or paste secret">
              <SecretInput
                value={form.totp_secret}
                onChange={set("totp_secret")}
                placeholder="JBSWY3DPEHPK3PXP..."
                disabled={busy}
              />
            </FieldRow>

            <FieldRow label="Backup / Recovery Codes" hint="one code per line">
              <SecretTextarea
                value={form.backup_codes}
                onChange={set("backup_codes")}
                placeholder={"a1b2c3-d4e5f6\ng7h8i9-j0k1l2\n..."}
                rows={5}
                disabled={busy}
              />
            </FieldRow>

            <SectionLabel label="Security Questions" />
            <SecurityQuestionPair
              index={1}
              question={form.security_question_1}
              answer={form.security_answer_1}
              onQuestion={set("security_question_1")}
              onAnswer={set("security_answer_1")}
              disabled={busy}
            />
            <SecurityQuestionPair
              index={2}
              question={form.security_question_2}
              answer={form.security_answer_2}
              onQuestion={set("security_question_2")}
              onAnswer={set("security_answer_2")}
              disabled={busy}
            />
            <SecurityQuestionPair
              index={3}
              question={form.security_question_3}
              answer={form.security_answer_3}
              onQuestion={set("security_question_3")}
              onAnswer={set("security_answer_3")}
              disabled={busy}
            />
          </CollapsibleSection>

          {/* ── API ACCESS ────────────────────────────────────────────────── */}
          <CollapsibleSection
            id="api-access"
            title="API ACCESS"
            subtitle="API keys, PAT tokens, OAuth credentials, bearer tokens"
            active={activeSection}
            toggle={toggleSection}
          >
            <FieldRow label="API Key / Secret" hint="program API credential">
              <SecretInput
                value={form.api_key}
                onChange={set("api_key")}
                placeholder="sk-••••••••••••••••"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Personal Access Token (PAT)" hint="GitHub-style PAT">
              <SecretInput
                value={form.pat_token}
                onChange={set("pat_token")}
                placeholder="ghp_••••••••••••"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="OAuth Client ID" hint="public, not a secret">
              <PlainInput
                value={form.oauth_client_id}
                onChange={set("oauth_client_id")}
                placeholder="client_id_xxxx"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="OAuth Client Secret" hint="secret">
              <SecretInput
                value={form.oauth_client_secret}
                onChange={set("oauth_client_secret")}
                placeholder="••••••••••••••"
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Bearer Token / JWT" hint="long-lived session token">
              <SecretInput
                value={form.bearer_token}
                onChange={set("bearer_token")}
                placeholder="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Session Cookie" hint="raw cookie value for replays">
              <SecretTextarea
                value={form.session_cookie}
                onChange={set("session_cookie")}
                placeholder="session=abc123; csrf=def456; ..."
                rows={3}
                disabled={busy}
              />
            </FieldRow>
          </CollapsibleSection>

          {/* ── NOTES ────────────────────────────────────────────────────── */}
          <CollapsibleSection
            id="notes"
            title="NOTES"
            subtitle="Analyst notes stored in DB (not in Vault, not secret)"
            active={activeSection}
            toggle={toggleSection}
          >
            <FieldRow label="Analyst Notes" hint="stored in database">
              <PlainTextarea
                value={form.notes}
                onChange={set("notes")}
                placeholder={"Account created 2026-05-01\nVerified with program team\nScope: *.example.com"}
                rows={4}
                disabled={busy}
              />
            </FieldRow>
            <FieldRow label="Additional Info" hint="stored in Vault">
              <PlainTextarea
                value={form.additional}
                onChange={set("additional")}
                placeholder="Any other relevant account information..."
                rows={3}
                disabled={busy}
              />
            </FieldRow>
          </CollapsibleSection>

          {/* ── Credential detail ─────────────────────────────────────────── */}
          {hunterCredential && (
            <div
              style={{
                marginTop: 16,
                padding: "8px 10px",
                background: C.greenFaint,
                border: `1px solid ${C.border}`,
                borderRadius: 3,
                fontSize: "0.62rem",
                color: C.greenDim,
                lineHeight: 1.7,
              }}
            >
              <div>ID: {hunterCredential.id}</div>
              <div>Last validated: {hunterCredential.last_validated ?? "never"}</div>
              <div>Last accessed: {hunterCredential.last_accessed_at ?? "never"}</div>
              <div>Access count: {hunterCredential.access_count}</div>
            </div>
          )}

        </div>

        {/* ── Footer actions ───────────────────────────────────────────────── */}
        <div
          style={{
            padding: "10px 16px",
            borderTop: `1px solid ${C.border}`,
            background: C.bg,
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
            flexShrink: 0,
          }}
        >
          <ActionButton
            onClick={handleSaveCredentials}
            loading={saveMutation.isPending}
            disabled={busy || !program}
          >
            ⊕ SAVE TO VAULT
          </ActionButton>

          {isConfigured && (
            <ActionButton
              onClick={handleValidate}
              loading={validateMutation.isPending}
              disabled={busy}
              variant="ghost"
            >
              ◎ VALIDATE
            </ActionButton>
          )}

          {isConfigured && (
            <ActionButton
              onClick={handleDelete}
              loading={deleteMutation.isPending}
              disabled={busy}
              variant="danger"
            >
              ⊗ DELETE
            </ActionButton>
          )}

          <div style={{ flex: 1 }} />

          <ActionButton onClick={onClose} variant="ghost" disabled={busy}>
            × CLOSE
          </ActionButton>
        </div>

        {/* ── Toast ─────────────────────────────────────────────────────────── */}
        {toast && (
          <div
            style={{
              position: "absolute",
              top: 56,
              left: "50%",
              transform: "translateX(-50%)",
              background: toast.ok ? "rgba(0,40,0,0.95)" : "rgba(40,0,0,0.95)",
              border: `1px solid ${toast.ok ? C.greenDim : C.redDim}`,
              borderRadius: 4,
              padding: "6px 14px",
              color: toast.ok ? C.green : C.red,
              fontSize: "0.68rem",
              fontFamily: "IBM Plex Mono, monospace",
              letterSpacing: "0.04em",
              zIndex: 10,
              pointerEvents: "none",
              maxWidth: "90%",
              textAlign: "center",
            }}
          >
            {toast.message}
          </div>
        )}
      </div>
    </>
  );
}

// ============================================================================
// CollapsibleSection
// ============================================================================
function CollapsibleSection({
  id,
  title,
  subtitle,
  children,
  active,
  toggle,
}: {
  id: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
  active: string | null;
  toggle: (id: string) => void;
}) {
  const expanded = active === null || active === id;
  return (
    <div
      style={{
        marginTop: 12,
        border: `1px solid ${expanded ? C.borderActive : C.border}`,
        borderRadius: 4,
        overflow: "hidden",
        transition: "border-color 0.15s ease",
      }}
    >
      <button
        type="button"
        onClick={() => toggle(id)}
        style={{
          width: "100%",
          background: expanded ? C.greenFaint : "rgba(0,0,0,0.3)",
          border: "none",
          borderBottom: expanded ? `1px solid ${C.border}` : "none",
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ color: expanded ? C.green : C.greenDim, fontSize: "0.65rem" }}>
          {expanded ? "▾" : "▸"}
        </span>
        <div>
          <div
            style={{
              fontSize: "0.65rem",
              letterSpacing: "0.15em",
              color: expanded ? C.green : C.greenDim,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: "0.58rem",
              color: C.muted,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          >
            {subtitle}
          </div>
        </div>
      </button>

      {expanded && (
        <div style={{ padding: "10px 12px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
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
// Platform-specific signup guides
// ============================================================================
type PlatformGuide = {
  name: string;
  steps: string[];
  tips: string[];
  requirements: string[];
};

const PLATFORM_GUIDES: Record<string, PlatformGuide> = {
  hackerone: {
    name: "HackerOne",
    steps: [
      "Create account at hackerone.com/users/sign_up",
      "Verify email address",
      "Set up 2FA — TOTP is required for many programs",
      "Complete your hacker profile (handle, bio, skills)",
      "Navigate to the program and click 'Join Program'",
      "Read and accept scope rules and responsible disclosure policy",
      "Check reputation / signal requirements before joining private programs",
    ],
    tips: [
      "Use a professional handle — program owners will see it on every report",
      "Enable 2FA immediately and store the TOTP secret in the 2FA section below",
      "Some programs are private / invite-only — check the policy URL",
      "Build signal (≥ 1.0) before targeting high-value private programs",
    ],
    requirements: ["Valid email address", "TOTP 2FA (required by many programs)", "Clean hacker reputation"],
  },
  bugcrowd: {
    name: "Bugcrowd",
    steps: [
      "Register at bugcrowd.com/user/sign_up",
      "Complete email verification",
      "Enable MFA on your account settings",
      "Navigate to the specific program page and click 'Join Program'",
      "Accept the Bugcrowd Researcher Terms of Service",
      "Review the program brief, allowed actions, and out-of-scope assets",
      "Link a payout method before submitting your first report",
    ],
    tips: [
      "Link a payout account early (PayPal / Payoneer supported)",
      "Some programs are private — you need a direct invite link from the program owner",
      "Check whether the program requires NDA acceptance in the brief",
      "Bugcrowd priority score affects your access to higher-tier programs",
    ],
    requirements: ["Valid email", "MFA recommended", "Payout account (PayPal / Payoneer)"],
  },
  intigriti: {
    name: "Intigriti",
    steps: [
      "Register at app.intigriti.com/register",
      "Complete email verification",
      "Fill out your researcher profile fully",
      "Browse programs and request access (private programs require approval)",
      "Wait for program admin approval (can take 1–3 days for private programs)",
      "Accept program-specific rules and scope",
      "Read in-scope and out-of-scope assets very carefully — Intigriti is strict",
    ],
    tips: [
      "EU-based platform — submissions are GDPR-compliant",
      "Private programs require admin approval — apply early",
      "Intigriti supports IBAN / SEPA for European payouts",
      "Hall of Fame recognition is automatic for valid HIGH/CRITICAL findings",
    ],
    requirements: ["Valid email", "Complete researcher profile", "Program-specific approval"],
  },
  synack: {
    name: "Synack Red Team",
    steps: [
      "Apply at synack.com/red-team (application-based, not open registration)",
      "Complete the rigorous skills assessment",
      "Pass background check — this can take 2–4 weeks",
      "Sign NDA and contractor agreement",
      "Complete mandatory platform onboarding and training modules",
      "Access programs exclusively via the SRT secure portal",
      "All findings must go through Synack triage before disclosure",
    ],
    tips: [
      "Synack is invitation-only — requires demonstrated offensive security skills",
      "Strong vetting process: background check, skills test, references",
      "Highest-value targets with structured, guaranteed payouts",
      "All work stays confidential — no public CVE disclosure without approval",
    ],
    requirements: ["Formal application + acceptance", "Background check passed", "NDA signed", "Contractor agreement"],
  },
  yeswehack: {
    name: "YesWeHack",
    steps: [
      "Register at yeswehack.com",
      "Verify email address and complete hacker profile",
      "Browse public programs or request access to private ones",
      "Accept program-specific rules and legal terms",
      "Review scope and start testing",
    ],
    tips: [
      "Strong European (French) platform with active private program network",
      "Response SLAs are contractually enforced — expect fast triage",
      "Payouts via Payoneer or SEPA bank transfer",
      "Active community — Discord available for researchers",
    ],
    requirements: ["Valid email", "Complete hacker profile"],
  },
  immunefi: {
    name: "Immunefi",
    steps: [
      "Register at immunefi.com",
      "Connect a Web3 wallet (MetaMask or WalletConnect recommended)",
      "Complete KYC if your payout tier requires it (usually >$5 000)",
      "Browse and accept the specific program's terms of service",
      "Submit findings via the structured vulnerability report form",
    ],
    tips: [
      "Web3 / blockchain security focus: smart contracts, DeFi, bridges, wallets",
      "Largest bug bounties in the industry — programs up to $10M+",
      "Payouts in crypto: ETH, USDC, or the project's native token",
      "Save your wallet seed phrase in the Mnemonic Passphrase field above",
      "Critical smart contract bugs can pay 6–7 figure bounties",
    ],
    requirements: ["Web3 wallet (MetaMask / WC)", "KYC for large payouts", "Blockchain security skills"],
  },
};

const DEFAULT_GUIDE: PlatformGuide = {
  name: "Program",
  steps: [
    "Visit the program's policy URL (see link above)",
    "Create a hunter account on the platform",
    "Verify email address and enable 2FA where available",
    "Apply to join the program if approval is required",
    "Accept the scope rules and responsible disclosure policy",
    "Save all credentials in the sections below before scanning",
  ],
  tips: [
    "Always read scope rules before testing — out-of-scope submissions are rejected",
    "Enable 2FA and store the TOTP secret in the 2FA & Recovery section",
    "Keep a complete record of all account credentials in Vault",
    "Validate credentials after saving using the VALIDATE button",
  ],
  requirements: ["Valid email address", "2FA recommended"],
};

// ============================================================================
// Password strength scorer
// ============================================================================
function scorePassword(pwd: string): { score: 0 | 1 | 2 | 3 | 4; label: string; color: string } {
  if (!pwd) return { score: 0, label: "", color: C.border };
  let s = 0;
  if (pwd.length >= 8) s++;
  if (pwd.length >= 14) s++;
  if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) s++;
  if (/\d/.test(pwd)) s++;
  if (/[^A-Za-z0-9]/.test(pwd)) s++;
  const score = Math.min(4, s) as 0 | 1 | 2 | 3 | 4;
  const labels: Record<number, string> = { 0: "", 1: "WEAK", 2: "FAIR", 3: "STRONG", 4: "VERY STRONG" };
  const colors: Record<number, string> = {
    0: C.border,
    1: C.red,
    2: C.orange,
    3: "#aacc00",
    4: C.green,
  };
  return { score, label: labels[score], color: colors[score] };
}

// ============================================================================
// PasswordStrengthBar
// ============================================================================
function PasswordStrengthBar({ password }: { password: string }) {
  const { score, label, color } = scorePassword(password);
  if (!password) return null;
  return (
    <div style={{ marginTop: 4 }}>
      <div
        style={{
          display: "flex",
          gap: 3,
          marginBottom: 2,
        }}
      >
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 3,
              borderRadius: 2,
              background: i <= score ? color : C.border,
              transition: "background 0.2s ease",
            }}
          />
        ))}
      </div>
      <div
        style={{
          fontSize: "0.58rem",
          color,
          fontFamily: "IBM Plex Mono, monospace",
          letterSpacing: "0.1em",
        }}
      >
        {label}
      </div>
    </div>
  );
}

// ============================================================================
// Clipboard copy hook
// ============================================================================
function useCopyToClipboard() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copy = (key: string, text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    });
  };
  return { copy, copiedKey };
}

// ============================================================================
// CopyButton
// ============================================================================
function CopyButton({
  keyId,
  text,
  copiedKey,
  onCopy,
}: {
  keyId: string;
  text: string;
  copiedKey: string | null;
  onCopy: (key: string, text: string) => void;
}) {
  const isCopied = copiedKey === keyId;
  return (
    <button
      type="button"
      onClick={() => onCopy(keyId, text)}
      title="Copy to clipboard"
      style={{
        background: "none",
        border: `1px solid ${isCopied ? C.greenDim : C.border}`,
        borderRadius: 2,
        color: isCopied ? C.green : C.muted,
        cursor: text ? "pointer" : "default",
        fontSize: "0.6rem",
        padding: "2px 5px",
        fontFamily: "IBM Plex Mono, monospace",
        letterSpacing: "0.06em",
        lineHeight: 1,
        transition: "all 0.15s ease",
        flexShrink: 0,
      }}
    >
      {isCopied ? "✓ copied" : "⎘ copy"}
    </button>
  );
}

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
// ReadinessChecklist — header row showing which sections have data
// ============================================================================
function ReadinessChecklist({
  hasSignupUrl,
  hasIdentity,
  isConfigured,
  hasNotes,
  isValidated,
}: {
  hasSignupUrl: boolean;
  hasIdentity: boolean;
  isConfigured: boolean;
  hasNotes: boolean;
  isValidated: boolean;
}) {
  const items: Array<{ label: string; done: boolean }> = [
    { label: "Setup", done: hasSignupUrl },
    { label: "Identity", done: hasIdentity },
    { label: "Credentials", done: isConfigured },
    { label: "Notes", done: hasNotes },
    { label: "Validated", done: isValidated },
  ];
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        padding: "6px 16px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(0,0,0,0.2)",
      }}
    >
      {items.map((item) => (
        <span
          key={item.label}
          style={{
            fontSize: "0.58rem",
            fontFamily: "IBM Plex Mono, monospace",
            letterSpacing: "0.06em",
            color: item.done ? C.green : C.muted,
            display: "flex",
            alignItems: "center",
            gap: 3,
          }}
        >
          <span style={{ fontSize: "0.5rem" }}>{item.done ? "◉" : "○"}</span>
          {item.label}
        </span>
      ))}
    </div>
  );
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
        flexShrink: 0,
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
// CollapsibleSection — with optional completion badge
// ============================================================================
function CollapsibleSection({
  id,
  title,
  subtitle,
  children,
  active,
  toggle,
  complete,
}: {
  id: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
  active: string | null;
  toggle: (id: string) => void;
  complete?: boolean;
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
        <div style={{ flex: 1 }}>
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
        {/* Completion badge */}
        {complete !== undefined && (
          <span
            style={{
              fontSize: "0.55rem",
              fontFamily: "IBM Plex Mono, monospace",
              color: complete ? C.green : C.muted,
              border: `1px solid ${complete ? C.borderActive : C.border}`,
              borderRadius: 2,
              padding: "1px 4px",
              letterSpacing: "0.06em",
            }}
          >
            {complete ? "✓ done" : "○ empty"}
          </span>
        )}
      </button>

      {expanded && (
        <div style={{ padding: "10px 12px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// PlatformGuideCard — shown inside ACCESS SETUP for known platforms
// ============================================================================
function PlatformGuideCard({ platform }: { platform: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const guide = platform ? (PLATFORM_GUIDES[platform.toLowerCase()] ?? DEFAULT_GUIDE) : DEFAULT_GUIDE;

  return (
    <div
      style={{
        marginBottom: 12,
        border: `1px solid ${C.border}`,
        borderRadius: 3,
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        style={{
          width: "100%",
          background: expanded ? "rgba(0,255,65,0.04)" : "rgba(0,0,0,0.25)",
          border: "none",
          borderBottom: expanded ? `1px solid ${C.border}` : "none",
          padding: "6px 10px",
          display: "flex",
          alignItems: "center",
          gap: 6,
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ color: C.greenDim, fontSize: "0.62rem" }}>{expanded ? "▾" : "▸"}</span>
        <span
          style={{
            color: C.greenDim,
            fontFamily: "IBM Plex Mono, monospace",
            fontSize: "0.62rem",
            letterSpacing: "0.1em",
          }}
        >
          {guide.name.toUpperCase()} SIGNUP GUIDE
        </span>
      </button>

      {expanded && (
        <div style={{ padding: "10px 12px" }}>
          {/* Steps */}
          <div
            style={{
              fontSize: "0.58rem",
              color: C.muted,
              letterSpacing: "0.08em",
              marginBottom: 4,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          >
            STEPS
          </div>
          <ol style={{ margin: "0 0 10px 0", paddingLeft: 18 }}>
            {guide.steps.map((step, i) => (
              <li
                key={i}
                style={{
                  color: C.greenDim,
                  fontFamily: "IBM Plex Mono, monospace",
                  fontSize: "0.68rem",
                  marginBottom: 3,
                  lineHeight: 1.5,
                }}
              >
                {step}
              </li>
            ))}
          </ol>

          {/* Requirements */}
          <div
            style={{
              fontSize: "0.58rem",
              color: C.muted,
              letterSpacing: "0.08em",
              marginBottom: 4,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          >
            REQUIREMENTS
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 10 }}>
            {guide.requirements.map((req) => (
              <span
                key={req}
                style={{
                  fontSize: "0.6rem",
                  fontFamily: "IBM Plex Mono, monospace",
                  color: C.greenDim,
                  border: `1px solid ${C.border}`,
                  borderRadius: 2,
                  padding: "1px 5px",
                }}
              >
                {req}
              </span>
            ))}
          </div>

          {/* Tips */}
          <div
            style={{
              fontSize: "0.58rem",
              color: C.muted,
              letterSpacing: "0.08em",
              marginBottom: 4,
              fontFamily: "IBM Plex Mono, monospace",
            }}
          >
            TIPS
          </div>
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {guide.tips.map((tip, i) => (
              <li
                key={i}
                style={{
                  color: C.greenDim,
                  fontFamily: "IBM Plex Mono, monospace",
                  fontSize: "0.66rem",
                  marginBottom: 3,
                  lineHeight: 1.5,
                }}
              >
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}
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
  const { copy, copiedKey } = useCopyToClipboard();

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

  // ── Derived staleness ─────────────────────────────────────────────────────
  const daysSinceValidated = useMemo(() => {
    if (!hunterCredential?.last_validated) return null;
    return Math.floor(
      (Date.now() - new Date(hunterCredential.last_validated).getTime()) / 86_400_000
    );
  }, [hunterCredential?.last_validated]);

  const isStale =
    isConfigured && (daysSinceValidated === null || daysSinceValidated > 30);

  // ── Mnemonic word count ────────────────────────────────────────────────────
  const mnemonicWordCount = useMemo(() => {
    const trimmed = form.mnemonic_passphrase.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }, [form.mnemonic_passphrase]);

  // ── Readiness indicators ──────────────────────────────────────────────────
  const hasSignupUrl = !!hunterMetadata?.signup_url;
  const hasIdentity = !!hunterCredential?.credential_username;
  const hasNotes = !!hunterCredential?.notes;
  const isValidated = !!hunterCredential?.last_validated;

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
          result.valid
            ? `Validation passed: ${result.reason}`
            : `Validation failed: ${result.reason}`,
          result.valid
        );
      },
      onError: (e) => showToast(`Validate error: ${(e as Error).message}`, false),
    });
  };

  const handleDelete = () => {
    if (
      !window.confirm(
        `Delete all hunter credentials for "${program?.name}"? This cannot be undone.`
      )
    )
      return;
    deleteMutation.mutate(undefined, {
      onSuccess: () => {
        showToast("Credentials deleted.", true);
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

  if (!open) return null;

  const busy =
    saveMutation.isPending || deleteMutation.isPending || validateMutation.isPending;

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
          width: "min(660px, 92vw)",
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
            <div
              style={{
                color: C.green,
                fontSize: "0.8rem",
                fontWeight: 600,
                letterSpacing: "0.04em",
              }}
            >
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

          <StatusBadge configured={isConfigured} status={hunterCredential?.status} />

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

        {/* ── Readiness checklist ──────────────────────────────────────────── */}
        <ReadinessChecklist
          hasSignupUrl={hasSignupUrl}
          hasIdentity={hasIdentity}
          isConfigured={isConfigured}
          hasNotes={hasNotes}
          isValidated={isValidated}
        />

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

          {/* ── Staleness warning ──────────────────────────────────────────── */}
          {isStale && (
            <div
              style={{
                marginTop: 12,
                padding: "8px 10px",
                background: "rgba(255,153,0,0.06)",
                border: "1px solid rgba(255,153,0,0.25)",
                borderRadius: 3,
                fontSize: "0.65rem",
                color: C.orange,
                fontFamily: "IBM Plex Mono, monospace",
                lineHeight: 1.6,
              }}
            >
              ⚠{" "}
              {daysSinceValidated === null
                ? "Credentials have never been validated. Use the VALIDATE button to confirm they work before scanning."
                : `Credentials last validated ${daysSinceValidated} days ago. Re-validate before scheduling a scan.`}
            </div>
          )}

          {/* ── ACCESS SETUP ──────────────────────────────────────────────── */}
          <CollapsibleSection
            id="access-setup"
            title="ACCESS SETUP"
            subtitle="Signup URL, instructions, and testing account info"
            active={activeSection}
            toggle={toggleSection}
            complete={hasSignupUrl}
          >
            {/* Platform guide card */}
            <PlatformGuideCard platform={program?.platform ?? null} />

            <FieldRow label="Program Policy URL" hint="from program listing">
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <a
                  href={program?.policy_url ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: C.green,
                    fontSize: "0.72rem",
                    textDecoration: "underline",
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {program?.policy_url ?? "No policy URL on record"}
                </a>
                {program?.policy_url && (
                  <CopyButton
                    keyId="policy_url"
                    text={program.policy_url}
                    copiedKey={copiedKey}
                    onCopy={copy}
                  />
                )}
              </div>
            </FieldRow>

            <FieldRow label="Signup / Registration URL">
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                  <PlainInput
                    value={form.signup_url}
                    onChange={set("signup_url")}
                    placeholder="https://hackerone.com/programs/..."
                    disabled={busy}
                  />
                </div>
                {form.signup_url && (
                  <>
                    <CopyButton
                      keyId="signup_url"
                      text={form.signup_url}
                      copiedKey={copiedKey}
                      onCopy={copy}
                    />
                    <a
                      href={form.signup_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: "0.62rem",
                        fontFamily: "IBM Plex Mono, monospace",
                        color: C.green,
                        border: `1px solid ${C.borderActive}`,
                        borderRadius: 2,
                        padding: "2px 6px",
                        textDecoration: "none",
                        whiteSpace: "nowrap",
                        letterSpacing: "0.06em",
                      }}
                    >
                      ↗ open
                    </a>
                  </>
                )}
              </div>
            </FieldRow>

            <FieldRow label="Account Creation Instructions" hint="shown before scanning">
              <PlainTextarea
                value={form.signup_instructions}
                onChange={set("signup_instructions")}
                placeholder={
                  "1. Visit signup URL above\n2. Create account with hunter email\n3. Complete email verification\n4. Apply to program's bug bounty scope\n5. Save credentials below"
                }
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
            complete={hasIdentity}
          >
            <FieldRow label="Username / Handle" hint="shown in status badge">
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                  <PlainInput
                    value={form.username}
                    onChange={set("username")}
                    placeholder="hunter_handle"
                    disabled={busy}
                  />
                </div>
                {form.username && (
                  <CopyButton
                    keyId="username"
                    text={form.username}
                    copiedKey={copiedKey}
                    onCopy={copy}
                  />
                )}
              </div>
            </FieldRow>
            <FieldRow label="Email Address" hint="stored in Vault">
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                  <PlainInput
                    value={form.email}
                    onChange={set("email")}
                    placeholder="hunter@email.com"
                    disabled={busy}
                  />
                </div>
                {form.email && (
                  <CopyButton
                    keyId="email"
                    text={form.email}
                    copiedKey={copiedKey}
                    onCopy={copy}
                  />
                )}
              </div>
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
            complete={isConfigured}
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
              ⚠ WRITE-ONLY — existing values are never retrieved. Only filled fields are written.
              Empty fields do not overwrite what is already in Vault.
            </div>

            <FieldRow label="Password" hint="main account password">
              <SecretInput
                value={form.password}
                onChange={set("password")}
                placeholder="Enter new password to overwrite"
                disabled={busy}
              />
              {/* Password strength bar */}
              <PasswordStrengthBar password={form.password} />
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
              {/* Word count indicator */}
              {form.mnemonic_passphrase.trim() && (
                <div
                  style={{
                    marginTop: 3,
                    fontSize: "0.6rem",
                    fontFamily: "IBM Plex Mono, monospace",
                    color:
                      mnemonicWordCount === 12 || mnemonicWordCount === 24
                        ? C.green
                        : mnemonicWordCount > 0
                          ? C.orange
                          : C.muted,
                    letterSpacing: "0.08em",
                  }}
                >
                  {mnemonicWordCount} word{mnemonicWordCount !== 1 ? "s" : ""}
                  {mnemonicWordCount === 12 && " ✓ (valid 12-word BIP-39)"}
                  {mnemonicWordCount === 24 && " ✓ (valid 24-word BIP-39)"}
                  {mnemonicWordCount > 0 &&
                    mnemonicWordCount !== 12 &&
                    mnemonicWordCount !== 24 &&
                    " — standard lengths are 12 or 24 words"}
                </div>
              )}
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
            <FieldRow label="TOTP Secret (Base32)" hint="scan QR or paste secret — used by authenticator apps">
              <SecretInput
                value={form.totp_secret}
                onChange={set("totp_secret")}
                placeholder="JBSWY3DPEHPK3PXP..."
                disabled={busy}
              />
              {form.totp_secret && (
                <div
                  style={{
                    marginTop: 3,
                    fontSize: "0.6rem",
                    fontFamily: "IBM Plex Mono, monospace",
                    color:
                      /^[A-Z2-7]+=*$/.test(form.totp_secret.toUpperCase()) &&
                      form.totp_secret.length >= 16
                        ? C.green
                        : C.orange,
                    letterSpacing: "0.06em",
                  }}
                >
                  {/^[A-Z2-7]+=*$/.test(form.totp_secret.toUpperCase()) &&
                  form.totp_secret.length >= 16
                    ? "✓ looks like valid Base32"
                    : "⚠ verify this is valid Base32 (A-Z, 2-7)"}
                </div>
              )}
            </FieldRow>

            <FieldRow label="Backup / Recovery Codes" hint="one code per line">
              <SecretTextarea
                value={form.backup_codes}
                onChange={set("backup_codes")}
                placeholder={"a1b2c3-d4e5f6\ng7h8i9-j0k1l2\n..."}
                rows={5}
                disabled={busy}
              />
              {form.backup_codes.trim() && (
                <div
                  style={{
                    marginTop: 3,
                    fontSize: "0.6rem",
                    fontFamily: "IBM Plex Mono, monospace",
                    color: C.greenDim,
                    letterSpacing: "0.06em",
                  }}
                >
                  {form.backup_codes.trim().split(/\n/).filter(Boolean).length} code
                  {form.backup_codes.trim().split(/\n/).filter(Boolean).length !== 1 ? "s" : ""} stored
                </div>
              )}
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
            <FieldRow label="OAuth Client ID" hint="public — not a secret">
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                  <PlainInput
                    value={form.oauth_client_id}
                    onChange={set("oauth_client_id")}
                    placeholder="client_id_xxxx"
                    disabled={busy}
                  />
                </div>
                {form.oauth_client_id && (
                  <CopyButton
                    keyId="oauth_client_id"
                    text={form.oauth_client_id}
                    copiedKey={copiedKey}
                    onCopy={copy}
                  />
                )}
              </div>
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
            complete={hasNotes}
          >
            <FieldRow label="Analyst Notes" hint="stored in database — visible in status">
              <PlainTextarea
                value={form.notes}
                onChange={set("notes")}
                placeholder={
                  "Account created 2026-05-01\nVerified with program team\nScope: *.example.com\nPayout: PayPal"
                }
                rows={4}
                disabled={busy}
              />
              {form.notes && (
                <div
                  style={{
                    marginTop: 3,
                    fontSize: "0.58rem",
                    color: C.muted,
                    fontFamily: "IBM Plex Mono, monospace",
                    textAlign: "right",
                  }}
                >
                  {form.notes.length} chars
                </div>
              )}
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

          {/* ── Credential metadata detail ────────────────────────────────── */}
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
              <div
                style={{
                  fontSize: "0.58rem",
                  color: C.muted,
                  letterSpacing: "0.12em",
                  marginBottom: 4,
                }}
              >
                VAULT RECORD
              </div>
              <div>ID: {hunterCredential.id}</div>
              <div>
                Last validated:{" "}
                {hunterCredential.last_validated
                  ? `${hunterCredential.last_validated} (${daysSinceValidated ?? 0}d ago)`
                  : "never"}
              </div>
              <div>
                Last accessed: {hunterCredential.last_accessed_at ?? "never"}
                {hunterCredential.last_accessed_by
                  ? ` by ${hunterCredential.last_accessed_by}`
                  : ""}
              </div>
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
              variant={isStale ? "warn" : "ghost"}
            >
              ◎ {isStale ? "VALIDATE NOW" : "VALIDATE"}
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

"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { listCredentials } from "@/lib/api/credentials";
import { queryKeys } from "@/lib/query-keys";
import type { ProgramOpportunity } from "@/lib/types/bug-bounty";
import { HunterAccountDrawer } from "@/components/credentials/HunterAccountDrawer";
import { PageHeader } from "@/components/layout/PageHeader";

// ── Colour palette ────────────────────────────────────────────────────────────
const C = {
  bg: "#0a0f0a",
  panel: "#0d140d",
  border: "#003300",
  borderActive: "#006600",
  green: "#00FF41",
  greenDim: "#007A1E",
  greenFaint: "rgba(0,255,65,0.07)",
  greenGlow: "rgba(0,255,65,0.35)",
  orange: "#ff9900",
  muted: "#004d10",
  red: "#ff4444",
  text: "#00e536",
  inputBg: "#060c06",
} as const;

// ── PlatformBadge ──────────────────────────────────────────────────────────────
function PlatformBadge({ platform }: { platform: string | null }) {
  if (!platform) return null;
  const colors: Record<string, string> = {
    hackerone: "#ff6600",
    bugcrowd: "#e84445",
    intigriti: "#5c2d91",
    synack: "#1565c0",
    yeswehack: "#00aa44",
    immunefi: "#FF4545",
  };
  const bg = colors[platform.toLowerCase()] ?? C.greenDim;
  return (
    <span
      style={{
        fontSize: "0.52rem",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color: "#fff",
        background: bg,
        borderRadius: 2,
        padding: "1px 5px",
        fontFamily: "IBM Plex Mono, monospace",
        flexShrink: 0,
      }}
    >
      {platform}
    </span>
  );
}

// ── CredentialStatusDot ────────────────────────────────────────────────────────
function CredentialStatusDot({ programId }: { programId: string }) {
  const query = useQuery({
    queryKey: queryKeys.credentials.forProgram(programId),
    queryFn: ({ signal }) => listCredentials(programId, signal),
    staleTime: 60_000,
  });

  const hunter = query.data?.credentials.find((c) => c.access_type === "hunter_account");
  if (query.isLoading) {
    return <span style={{ color: C.muted, fontSize: "0.55rem" }}>●</span>;
  }
  if (!hunter) {
    return (
      <span title="No hunter account configured" style={{ color: C.muted, fontSize: "0.55rem" }}>
        ○
      </span>
    );
  }
  const dotColor =
    hunter.status === "active"
      ? C.green
      : hunter.status === "needs_renewal"
        ? C.orange
        : C.red;
  return (
    <span
      title={`Hunter account: ${hunter.status}`}
      style={{
        color: dotColor,
        fontSize: "0.55rem",
        textShadow: hunter.status === "active" ? `0 0 4px ${dotColor}` : "none",
      }}
    >
      ●
    </span>
  );
}

// ── ProgramCard ────────────────────────────────────────────────────────────────
function ProgramCard({
  program,
  selected,
  onClick,
}: {
  program: ProgramOpportunity;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: "100%",
        background: selected ? C.greenFaint : "rgba(0,0,0,0.4)",
        border: `1px solid ${selected ? C.borderActive : C.border}`,
        borderRadius: 4,
        padding: "10px 12px",
        textAlign: "left",
        cursor: "pointer",
        fontFamily: "IBM Plex Mono, monospace",
        display: "flex",
        alignItems: "center",
        gap: 10,
        transition: "all 0.1s ease",
        boxShadow: selected ? `inset 0 0 8px rgba(0,255,65,0.04)` : "none",
      }}
    >
      {/* Status dot */}
      <CredentialStatusDot programId={program.id} />

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            color: selected ? C.green : C.text,
            fontSize: "0.75rem",
            fontWeight: 600,
            letterSpacing: "0.02em",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {program.name}
        </div>
        {program.handle && (
          <div
            style={{
              color: C.greenDim,
              fontSize: "0.62rem",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            @{program.handle}
          </div>
        )}
      </div>

      {/* Platform + status */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3, flexShrink: 0 }}>
        <PlatformBadge platform={program.platform} />
        <span
          style={{
            fontSize: "0.52rem",
            color: program.status === "active" ? C.greenDim : C.muted,
            letterSpacing: "0.06em",
          }}
        >
          {program.status?.toUpperCase()}
        </span>
      </div>

      {/* Arrow */}
      <span style={{ color: selected ? C.green : C.muted, fontSize: "0.65rem" }}>›</span>
    </button>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function HunterAccountsPage() {
  const [selectedProgram, setSelectedProgram] = useState<ProgramOpportunity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("ALL");

  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal),
    staleTime: 120_000,
  });

  const programs = programsQuery.data ?? [];

  const platforms = useMemo(() => {
    const set = new Set<string>();
    for (const p of programs) {
      if (p.platform) set.add(p.platform);
    }
    return Array.from(set).sort();
  }, [programs]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return programs.filter((p) => {
      if (platformFilter !== "ALL" && p.platform !== platformFilter) return false;
      if (!term) return true;
      const hay = [p.name, p.handle, p.platform, p.program_key]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(term);
    });
  }, [programs, search, platformFilter]);

  const handleSelect = (program: ProgramOpportunity) => {
    setSelectedProgram(program);
    setDrawerOpen(true);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        color: C.green,
        fontFamily: "IBM Plex Mono, monospace",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 16px" }}>
        <PageHeader
          title="Hunter Accounts"
          description="Manage bug bounty hunter accounts and credentials for each program. All secrets stored in HashiCorp Vault."
        />

        {/* ── Stats bar ── */}
        <div
          style={{
            display: "flex",
            gap: 16,
            marginBottom: 16,
            padding: "8px 12px",
            background: C.panel,
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            fontSize: "0.65rem",
            color: C.greenDim,
            letterSpacing: "0.08em",
          }}
        >
          <span>
            PROGRAMS:{" "}
            <span style={{ color: C.green }}>{programs.length}</span>
          </span>
          <span>
            FILTERED:{" "}
            <span style={{ color: C.green }}>{filtered.length}</span>
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ color: C.muted }}>
            ● CONFIGURED &nbsp; ○ NOT CONFIGURED
          </span>
        </div>

        {/* ── Filters ── */}
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search programs..."
            style={{
              flex: "1 1 180px",
              background: C.inputBg,
              border: `1px solid ${C.border}`,
              borderRadius: 3,
              color: C.green,
              fontFamily: "IBM Plex Mono, monospace",
              fontSize: "0.72rem",
              padding: "6px 10px",
              outline: "none",
            }}
          />
          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            style={{
              background: C.inputBg,
              border: `1px solid ${C.border}`,
              borderRadius: 3,
              color: C.greenDim,
              fontFamily: "IBM Plex Mono, monospace",
              fontSize: "0.72rem",
              padding: "6px 8px",
              outline: "none",
            }}
          >
            <option value="ALL">All platforms</option>
            {platforms.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* ── Program list ── */}
        {programsQuery.isLoading && (
          <div
            style={{
              padding: "24px",
              textAlign: "center",
              color: C.muted,
              fontSize: "0.72rem",
              letterSpacing: "0.1em",
            }}
          >
            ⟳ Loading programs...
          </div>
        )}

        {programsQuery.isError && (
          <div
            style={{
              padding: "12px",
              background: "rgba(255,68,68,0.05)",
              border: "1px solid rgba(255,68,68,0.2)",
              borderRadius: 4,
              color: C.red,
              fontSize: "0.7rem",
            }}
          >
            ⊗ Failed to load programs:{" "}
            {(programsQuery.error as Error)?.message ?? "Unknown error"}
          </div>
        )}

        {!programsQuery.isLoading && filtered.length === 0 && (
          <div
            style={{
              padding: "32px",
              textAlign: "center",
              color: C.muted,
              fontSize: "0.72rem",
              border: `1px solid ${C.border}`,
              borderRadius: 4,
            }}
          >
            {programs.length === 0
              ? "No programs found. Add a program in Programs / Targets first."
              : "No programs match the current filters."}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map((program) => (
            <ProgramCard
              key={program.id}
              program={program}
              selected={selectedProgram?.id === program.id && drawerOpen}
              onClick={() => handleSelect(program)}
            />
          ))}
        </div>

        {/* ── Guide panel (shown when no program selected) ── */}
        {!drawerOpen && (
          <div
            style={{
              marginTop: 24,
              padding: "16px",
              background: C.panel,
              border: `1px solid ${C.border}`,
              borderRadius: 4,
              fontSize: "0.68rem",
              color: C.greenDim,
              lineHeight: 1.8,
            }}
          >
            <div
              style={{
                fontSize: "0.62rem",
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                color: C.greenDim,
                marginBottom: 8,
                borderBottom: `1px solid ${C.border}`,
                paddingBottom: 6,
              }}
            >
              ◈ HUNTER ACCOUNT SETUP GUIDE
            </div>
            <ol style={{ paddingLeft: 16, margin: 0 }}>
              <li>
                <span style={{ color: C.green }}>Select a program</span> from the list above to
                open its account management panel.
              </li>
              <li>
                In the <span style={{ color: C.green }}>ACCESS SETUP</span> section, enter the
                program&apos;s signup URL and step-by-step account creation instructions.
              </li>
              <li>
                Create your hunter account on the platform{" "}
                <span style={{ color: C.green }}>before scanning</span> — many programs require
                prior registration and NDA acceptance.
              </li>
              <li>
                Fill in your credentials: username, email, password, 2FA secrets, API keys, and
                any PAT tokens.
              </li>
              <li>
                Click <span style={{ color: C.green }}>SAVE TO VAULT</span> — all secrets are
                encrypted and stored in HashiCorp Vault. Only metadata
                (username, status) is kept in the database.
              </li>
              <li>
                Use <span style={{ color: C.green }}>VALIDATE</span> to confirm the credentials
                work before launching a scan.
              </li>
            </ol>
            <div
              style={{
                marginTop: 12,
                padding: "6px 10px",
                background: "rgba(255,153,0,0.05)",
                border: "1px solid rgba(255,153,0,0.15)",
                borderRadius: 3,
                color: C.orange,
                fontSize: "0.62rem",
              }}
            >
              ⚠ Without a valid hunter account, authenticated scans and bug bounty submissions
              will fail. Configure accounts before scheduling scans.
            </div>
          </div>
        )}
      </div>

      {/* ── Drawer ── */}
      <HunterAccountDrawer
        program={selectedProgram}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}

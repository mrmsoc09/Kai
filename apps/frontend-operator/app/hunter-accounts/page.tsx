"use client";

import { useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

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
  orange: "#ff9900",
  muted: "#004d10",
  red: "#ff4444",
  text: "#00e536",
  inputBg: "#060c06",
} as const;

// ── SortOrder ─────────────────────────────────────────────────────────────────
type SortOrder = "name" | "platform" | "newest" | "configured";

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

// ── CredentialInfo — per-program credential status for display ─────────────────
type CredentialInfo = {
  status: "active" | "expired" | "invalid" | "needs_renewal" | null;
  username: string | null;
  lastValidated: string | null;
  isConfigured: boolean;
  isStale: boolean;
};

// ── StatsBar ──────────────────────────────────────────────────────────────────
function StatsBar({
  total,
  filtered,
  configured,
  validated,
  needsAttention,
  loading,
}: {
  total: number;
  filtered: number;
  configured: number;
  validated: number;
  needsAttention: number;
  loading: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 0,
        marginBottom: 14,
        border: `1px solid ${C.border}`,
        borderRadius: 4,
        overflow: "hidden",
        fontFamily: "IBM Plex Mono, monospace",
      }}
    >
      {[
        { label: "TOTAL", value: total, color: C.greenDim },
        { label: "FILTERED", value: filtered, color: C.greenDim },
        { label: "CONFIGURED", value: configured, color: C.green },
        { label: "VALIDATED", value: validated, color: C.green },
        { label: "NEEDS ATTENTION", value: needsAttention, color: needsAttention > 0 ? C.orange : C.muted },
      ].map((stat, idx, arr) => (
        <div
          key={stat.label}
          style={{
            flex: 1,
            padding: "8px 10px",
            background: C.panel,
            borderRight: idx < arr.length - 1 ? `1px solid ${C.border}` : "none",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "0.6rem",
              color: C.muted,
              letterSpacing: "0.1em",
              marginBottom: 2,
            }}
          >
            {stat.label}
          </div>
          <div
            style={{
              fontSize: "1rem",
              fontWeight: 700,
              color: loading ? C.muted : stat.color,
              letterSpacing: "0.04em",
            }}
          >
            {loading ? "—" : stat.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── ProgramCard ────────────────────────────────────────────────────────────────
function ProgramCard({
  program,
  credInfo,
  selected,
  onClick,
}: {
  program: ProgramOpportunity;
  credInfo: CredentialInfo | undefined;
  selected: boolean;
  onClick: () => void;
}) {
  const dotColor =
    !credInfo || !credInfo.isConfigured
      ? C.muted
      : credInfo.status === "active"
        ? C.green
        : credInfo.status === "needs_renewal"
          ? C.orange
          : C.red;

  const dotTitle =
    !credInfo || !credInfo.isConfigured
      ? "No hunter account configured"
      : `Hunter account: ${credInfo.status}`;

  // Relative time for last validated
  const validatedLabel = useMemo(() => {
    if (!credInfo?.lastValidated) return null;
    const days = Math.floor(
      (Date.now() - new Date(credInfo.lastValidated).getTime()) / 86_400_000
    );
    if (days === 0) return "validated today";
    if (days === 1) return "validated yesterday";
    if (days < 30) return `validated ${days}d ago`;
    if (days < 365) return `validated ${Math.floor(days / 30)}mo ago`;
    return `validated ${Math.floor(days / 365)}y ago`;
  }, [credInfo?.lastValidated]);

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
      <span
        title={dotTitle}
        style={{
          color: dotColor,
          fontSize: "0.55rem",
          textShadow:
            credInfo?.isConfigured && credInfo.status === "active"
              ? `0 0 4px ${dotColor}`
              : "none",
          flexShrink: 0,
        }}
      >
        {credInfo?.isConfigured ? "●" : "○"}
      </span>

      {/* Program info */}
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
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginTop: 2,
          }}
        >
          {program.handle && (
            <span style={{ color: C.greenDim, fontSize: "0.62rem" }}>
              @{program.handle}
            </span>
          )}
          {credInfo?.username && (
            <span
              style={{
                fontSize: "0.58rem",
                color: C.green,
                border: `1px solid ${C.border}`,
                borderRadius: 2,
                padding: "0px 4px",
                letterSpacing: "0.06em",
              }}
            >
              ⚿ {credInfo.username}
            </span>
          )}
          {credInfo?.isStale && (
            <span
              style={{
                fontSize: "0.55rem",
                color: C.orange,
                letterSpacing: "0.06em",
              }}
              title="Credentials stale — re-validate before scanning"
            >
              ⚠ stale
            </span>
          )}
        </div>
      </div>

      {/* Right column */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 3,
          flexShrink: 0,
        }}
      >
        <PlatformBadge platform={program.platform} />
        <span
          style={{
            fontSize: "0.52rem",
            color:
              program.status === "active" ? C.greenDim : C.muted,
            letterSpacing: "0.06em",
          }}
        >
          {program.status?.toUpperCase()}
        </span>
        {validatedLabel && (
          <span
            style={{
              fontSize: "0.52rem",
              color: C.muted,
              letterSpacing: "0.04em",
            }}
          >
            {validatedLabel}
          </span>
        )}
      </div>

      {/* Chevron */}
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
  const [sortOrder, setSortOrder] = useState<SortOrder>("name");

  // ── Programs query ─────────────────────────────────────────────────────────
  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal),
    staleTime: 120_000,
  });
  const programs = programsQuery.data ?? [];

  // ── Batch credential status — one query per program (cached by dot components) ──
  const credQueries = useQueries({
    queries: programs.map((p) => ({
      queryKey: queryKeys.credentials.forProgram(p.id),
      queryFn: ({ signal }: { signal: AbortSignal }) => listCredentials(p.id, signal),
      staleTime: 60_000,
    })),
  });

  // ── Build a Map of programId → CredentialInfo ──────────────────────────────
  const credMap = useMemo<Map<string, CredentialInfo>>(() => {
    const map = new Map<string, CredentialInfo>();
    programs.forEach((p, idx) => {
      const q = credQueries[idx];
      if (!q?.data) return;
      const hunter = q.data.credentials.find((c) => c.access_type === "hunter_account");
      if (!hunter) {
        map.set(p.id, {
          status: null,
          username: null,
          lastValidated: null,
          isConfigured: false,
          isStale: false,
        });
        return;
      }
      const daysSince = hunter.last_validated
        ? Math.floor(
            (Date.now() - new Date(hunter.last_validated).getTime()) / 86_400_000
          )
        : null;
      map.set(p.id, {
        status: hunter.status as CredentialInfo["status"],
        username: hunter.credential_username,
        lastValidated: hunter.last_validated,
        isConfigured: true,
        isStale: daysSince === null || daysSince > 30,
      });
    });
    return map;
  }, [programs, credQueries]);

  // ── Aggregate stats ────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    let configured = 0;
    let validated = 0;
    let needsAttention = 0;
    for (const info of credMap.values()) {
      if (info.isConfigured) {
        configured++;
        if (info.lastValidated) validated++;
        if (info.status !== "active") needsAttention++;
      }
    }
    return { configured, validated, needsAttention };
  }, [credMap]);

  const credQueriesLoading = credQueries.some((q) => q.isLoading);

  // ── Platform list for filter ───────────────────────────────────────────────
  const platforms = useMemo(() => {
    const set = new Set<string>();
    for (const p of programs) {
      if (p.platform) set.add(p.platform);
    }
    return Array.from(set).sort();
  }, [programs]);

  // ── Filter ─────────────────────────────────────────────────────────────────
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

  // ── Sort ───────────────────────────────────────────────────────────────────
  const sorted = useMemo(() => {
    return filtered.slice().sort((a, b) => {
      switch (sortOrder) {
        case "platform":
          return (a.platform ?? "zzz").localeCompare(b.platform ?? "zzz");
        case "newest":
          return (
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          );
        case "configured": {
          // Configured first, then not configured; within each group sort by name
          const aConf = credMap.get(a.id)?.isConfigured ? 0 : 1;
          const bConf = credMap.get(b.id)?.isConfigured ? 0 : 1;
          if (aConf !== bConf) return aConf - bConf;
          return a.name.localeCompare(b.name);
        }
        case "name":
        default:
          return a.name.localeCompare(b.name);
      }
    });
  }, [filtered, sortOrder, credMap]);

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
        <StatsBar
          total={programs.length}
          filtered={sorted.length}
          configured={stats.configured}
          validated={stats.validated}
          needsAttention={stats.needsAttention}
          loading={credQueriesLoading}
        />

        {/* ── Filters + Sort ── */}
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          {/* Search */}
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

          {/* Platform filter */}
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

          {/* Sort */}
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
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
            <option value="name">Sort: Name A→Z</option>
            <option value="platform">Sort: Platform</option>
            <option value="newest">Sort: Newest</option>
            <option value="configured">Sort: Configured First</option>
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

        {!programsQuery.isLoading && sorted.length === 0 && (
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
          {sorted.map((program) => (
            <ProgramCard
              key={program.id}
              program={program}
              credInfo={credMap.get(program.id)}
              selected={selectedProgram?.id === program.id && drawerOpen}
              onClick={() => handleSelect(program)}
            />
          ))}
        </div>

        {/* ── Setup guide (shown when no drawer open) ── */}
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
                <span style={{ color: C.green }}>Select a program</span> from the list above
                to open its account management panel.
              </li>
              <li>
                In <span style={{ color: C.green }}>ACCESS SETUP</span>, enter the program&apos;s
                signup URL and step-by-step account creation instructions. Each platform has a
                built-in signup guide to walk you through.
              </li>
              <li>
                Create your hunter account on the platform{" "}
                <span style={{ color: C.green }}>before scanning</span> — many programs require
                prior registration and NDA acceptance.
              </li>
              <li>
                Fill in your credentials in each section: username, email, password, 2FA TOTP
                secret, backup codes, security questions, API keys, and PAT tokens.
              </li>
              <li>
                Click <span style={{ color: C.green }}>SAVE TO VAULT</span> — all secrets are
                encrypted in HashiCorp Vault. Only the username and status are stored in the DB.
              </li>
              <li>
                Use <span style={{ color: C.green }}>VALIDATE</span> to confirm the credentials
                work before launching a scan. Credentials older than 30 days show a staleness
                warning.
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
              will fail. Use <strong>Sort: Configured First</strong> to quickly see which programs
              still need accounts set up.
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

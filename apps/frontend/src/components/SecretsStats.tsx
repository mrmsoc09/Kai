/**
 * SecretsStats Component
 * Displays statistics about secrets
 */

import React from "react";
import {
  Grid,
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  CircularProgress,
} from "@mui/material";
import {
  Lock,
  CheckCircle,
  Clock,
  RefreshCw,
  Database,
  Shield,
} from "lucide-react";
import { Secret, VaultHealthResponse } from "../types/vault";

interface SecretsStatsProps {
  secrets: Secret[];
  vaultStatus?: VaultHealthResponse | null;
  loading?: boolean;
}

interface StatCard {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
  secondaryText?: string;
}

/**
 * SecretsStats Component
 */
export function SecretsStats({
  secrets,
  vaultStatus,
  loading = false,
}: SecretsStatsProps) {
  const storedSecrets = secrets.filter((s) => s.status === "stored").length;
  const expiringSecrets = secrets.filter(
    (s) => s.status === "expires_soon",
  ).length;
  const missingSecrets = secrets.filter((s) => s.status === "missing").length;

  const lastUpdated =
    secrets.length > 0
      ? new Date(Math.max(...secrets.map((s) => s.lastUpdated.getTime())))
      : new Date();

  const getTimeAgo = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const stats: StatCard[] = [
    {
      icon: <Lock className="w-6 h-6" />,
      label: "Total Secrets",
      value: `${storedSecrets}/${secrets.length}`,
      color: "#0284C7",
      secondaryText: `${storedSecrets} stored`,
    },
    {
      icon: <CheckCircle className="w-6 h-6" />,
      label: "Critical Status",
      value: `${Math.max(0, 3 - missingSecrets)}/3`,
      color: storedSecrets > 0 ? "#10B981" : "#EF4444",
      secondaryText:
        missingSecrets > 0
          ? `${missingSecrets} missing`
          : "All critical secrets stored",
    },
    {
      icon: <Clock className="w-6 h-6" />,
      label: "Expiring Soon",
      value: expiringSecrets,
      color: expiringSecrets > 0 ? "#F59E0B" : "#10B981",
      secondaryText:
        expiringSecrets > 0
          ? `Check expiration dates`
          : "No secrets expiring soon",
    },
    {
      icon: <RefreshCw className="w-6 h-6" />,
      label: "Last Updated",
      value: getTimeAgo(lastUpdated),
      color: "#6B7280",
      secondaryText: lastUpdated.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }),
    },
    {
      icon: <Database className="w-6 h-6" />,
      label: "Vault Connection",
      value: vaultStatus?.connected ? "Connected" : "Disconnected",
      color: vaultStatus?.connected ? "#10B981" : "#EF4444",
      secondaryText: vaultStatus?.status || "Checking status...",
    },
    {
      icon: <Shield className="w-6 h-6" />,
      label: "Encryption",
      value: "AES-256-GCM",
      color: "#10B981",
      secondaryText: "FIPS 140-2 Compliant",
    },
  ];

  if (loading) {
    return (
      <Grid container spacing={2}>
        {[...Array(6)].map((_, i) => (
          <Grid item xs={12} sm={6} md={4} key={i}>
            <Card>
              <CardContent
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: "150px",
                }}
              >
                <CircularProgress size={32} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  }

  return (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {stats.map((stat, index) => (
        <Grid item xs={12} sm={6} md={4} key={index}>
          <Card
            sx={{
              height: "100%",
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#fff",
              border: "1px solid #e5e7eb",
              transition: "all 0.2s ease-in-out",
              "&:hover": {
                boxShadow: "0 4px 12px rgba(0, 0, 0, 0.08)",
                borderColor: stat.color,
              },
            }}
          >
            <CardContent sx={{ p: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  mb: 2,
                }}
              >
                <Box
                  sx={{
                    color: stat.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 40,
                    height: 40,
                    borderRadius: "0.5rem",
                    backgroundColor: `${stat.color}15`,
                  }}
                >
                  {stat.icon}
                </Box>
              </Box>

              <Typography
                sx={{
                  fontSize: "0.875rem",
                  color: "#6b7280",
                  fontWeight: 500,
                  mb: 0.5,
                }}
              >
                {stat.label}
              </Typography>

              <Typography
                sx={{
                  fontSize: "1.875rem",
                  fontWeight: 700,
                  color: "#1f2937",
                  mb: 1,
                }}
              >
                {stat.value}
              </Typography>

              {stat.secondaryText && (
                <Typography
                  sx={{
                    fontSize: "0.75rem",
                    color: "#9ca3af",
                    fontWeight: 400,
                  }}
                >
                  {stat.secondaryText}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
}

/**
 * AdvancedOptions Component
 * Collapsible section with advanced Vault operations
 */

import React, { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Button,
  Collapse,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  Chip,
} from "@mui/material";
import {
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Download,
  Clock,
  LogCheck,
  Activity,
  AlertCircle,
} from "lucide-react";

interface AdvancedOptionsProps {
  onRefresh?: () => Promise<void>;
  onExport?: () => Promise<Blob>;
  onGetAuditLog?: () => Promise<
    Array<{
      timestamp: string;
      action: string;
      secret: string;
      user?: string;
    }>
  >;
  onGetHealth?: () => Promise<any>;
}

/**
 * AdvancedOptions Component
 */
export function AdvancedOptions({
  onRefresh,
  onExport,
  onGetAuditLog,
  onGetHealth,
}: AdvancedOptionsProps) {
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [auditDialogOpen, setAuditDialogOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [healthDialogOpen, setHealthDialogOpen] = useState(false);
  const [healthData, setHealthData] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  const handleRefresh = async () => {
    if (!onRefresh) return;
    setRefreshing(true);
    try {
      await onRefresh();
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleExport = async () => {
    if (!onExport) return;
    setExporting(true);
    try {
      const blob = await onExport();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `vault-secrets-metadata-${Date.now()}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setExporting(false);
    }
  };

  const handleShowAuditLog = async () => {
    if (!onGetAuditLog) return;
    setAuditDialogOpen(true);
    setAuditLoading(true);
    setAuditError(null);
    try {
      const logs = await onGetAuditLog();
      setAuditLogs(logs);
    } catch (err) {
      setAuditError(
        err instanceof Error ? err.message : "Failed to fetch audit log",
      );
    } finally {
      setAuditLoading(false);
    }
  };

  const handleShowHealth = async () => {
    if (!onGetHealth) return;
    setHealthDialogOpen(true);
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await onGetHealth();
      setHealthData(data);
    } catch (err) {
      setHealthError(
        err instanceof Error ? err.message : "Failed to fetch health status",
      );
    } finally {
      setHealthLoading(false);
    }
  };

  return (
    <Card sx={{ mt: 3, bgcolor: "#f9fafb" }}>
      <Box
        sx={{
          p: 2,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
          "&:hover": { bgcolor: "#f3f4f6" },
          transition: "background-color 0.2s",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box
          sx={{ fontWeight: 600, color: "#1f2937", display: "flex", gap: 1 }}
        >
          <Settings className="w-5 h-5" />
          Advanced Options
        </Box>
        <IconButton size="small" sx={{ p: 0 }}>
          {expanded ? (
            <ChevronUp className="w-5 h-5" />
          ) : (
            <ChevronDown className="w-5 h-5" />
          )}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <CardContent sx={{ pt: 0, display: "flex", gap: 2, flexWrap: "wrap" }}>
          <Button
            startIcon={<RefreshCw className="w-4 h-4" />}
            variant="outlined"
            onClick={handleRefresh}
            disabled={refreshing || !onRefresh}
          >
            {refreshing ? "Refreshing..." : "Refresh from Vault"}
          </Button>

          <Button
            startIcon={<Download className="w-4 h-4" />}
            variant="outlined"
            onClick={handleExport}
            disabled={exporting || !onExport}
          >
            {exporting ? "Exporting..." : "Export Inventory"}
          </Button>

          <Button
            startIcon={<Clock className="w-4 h-4" />}
            variant="outlined"
            disabled={true}
            title="Coming soon"
          >
            Rotation Schedule
          </Button>

          <Button
            startIcon={<LogCheck className="w-4 h-4" />}
            variant="outlined"
            onClick={handleShowAuditLog}
            disabled={!onGetAuditLog}
          >
            Audit Log
          </Button>

          <Button
            startIcon={<Activity className="w-4 h-4" />}
            variant="outlined"
            onClick={handleShowHealth}
            disabled={!onGetHealth}
          >
            Vault Health
          </Button>
        </CardContent>
      </Collapse>

      {/* Audit Log Dialog */}
      <Dialog
        open={auditDialogOpen}
        onClose={() => setAuditDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Audit Log</DialogTitle>
        <DialogContent>
          {auditError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {auditError}
            </Alert>
          )}
          {auditLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress />
            </Box>
          ) : auditLogs.length === 0 ? (
            <Alert severity="info">No audit logs available</Alert>
          ) : (
            <TableContainer component={Paper} sx={{ mt: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: "#f3f4f6" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Timestamp</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Secret</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {auditLogs.slice(0, 20).map((log, idx) => (
                    <TableRow key={idx}>
                      <TableCell sx={{ fontSize: "0.875rem" }}>
                        {new Date(log.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.875rem" }}>
                        {log.action}
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.875rem" }}>
                        {log.secret}
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.875rem" }}>
                        {log.user || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAuditDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Health Dialog */}
      <Dialog
        open={healthDialogOpen}
        onClose={() => setHealthDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Vault Health Status</DialogTitle>
        <DialogContent>
          {healthError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {healthError}
            </Alert>
          )}
          {healthLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress />
            </Box>
          ) : healthData ? (
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}
            >
              <Box>
                <Box sx={{ fontSize: "0.875rem", color: "#6b7280", mb: 0.5 }}>
                  Status
                </Box>
                <Chip
                  label={healthData.status}
                  color={healthData.connected ? "success" : "error"}
                />
              </Box>
              {healthData.version && (
                <Box>
                  <Box sx={{ fontSize: "0.875rem", color: "#6b7280", mb: 0.5 }}>
                    Version
                  </Box>
                  <Box sx={{ fontFamily: "monospace", fontSize: "0.875rem" }}>
                    {healthData.version}
                  </Box>
                </Box>
              )}
              {healthData.sealed !== undefined && (
                <Box>
                  <Box sx={{ fontSize: "0.875rem", color: "#6b7280", mb: 0.5 }}>
                    Sealed
                  </Box>
                  <Chip
                    label={healthData.sealed ? "Sealed" : "Unsealed"}
                    color={healthData.sealed ? "error" : "success"}
                  />
                </Box>
              )}
            </Box>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHealthDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

// Icon placeholder
import { Settings } from "lucide-react";

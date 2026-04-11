/**
 * SecretsTable Component
 * Displays stored secrets in a table with actions
 */

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  CircularProgress,
  Typography,
} from "@mui/material";
import {
  MoreVertical,
  CheckCircle,
  AlertCircle,
  Clock,
  Trash2,
  Eye,
  Copy,
} from "lucide-react";
import { Secret } from "../types/vault";

interface SecretsTableProps {
  secrets: Secret[];
  loading?: boolean;
  onDelete: (name: string) => Promise<void>;
  onRefresh?: () => void;
}

/**
 * SecretsTable Component
 */
export function SecretsTable({
  secrets,
  loading = false,
  onDelete,
  onRefresh,
}: SecretsTableProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedSecret, setSelectedSecret] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleMenuOpen = (
    event: React.MouseEvent<HTMLElement>,
    name: string,
  ) => {
    setAnchorEl(event.currentTarget);
    setSelectedSecret(name);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedSecret(null);
  };

  const handleDeleteClick = (name: string) => {
    setDeleteConfirm(name);
    handleMenuClose();
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await onDelete(deleteConfirm);
      setDeleteConfirm(null);
    } catch (error) {
      console.error("Failed to delete secret:", error);
    } finally {
      setDeleting(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "stored":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "expires_soon":
        return <Clock className="w-5 h-5 text-amber-600" />;
      case "missing":
        return <AlertCircle className="w-5 h-5 text-red-600" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "stored":
        return "success";
      case "expires_soon":
        return "warning";
      case "missing":
        return "error";
      default:
        return "default";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "stored":
        return "Stored";
      case "expires_soon":
        return "Expires Soon";
      case "missing":
        return "Missing";
      default:
        return status;
    }
  };

  const formatDate = (date: Date | undefined) => {
    if (!date) return "-";
    return new Date(date).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (secrets.length === 0 && !loading) {
    return (
      <Paper sx={{ p: 3, textAlign: "center", bgcolor: "#f9fafb" }}>
        <Lock className="w-12 h-12 mx-auto mb-3 text-gray-400" />
        <Typography variant="h6" sx={{ color: "#6b7280", mb: 1 }}>
          No Secrets Configured
        </Typography>
        <Typography variant="body2" sx={{ color: "#9ca3af" }}>
          Add your first secret to get started.
        </Typography>
      </Paper>
    );
  }

  if (loading) {
    return (
      <Paper sx={{ p: 3, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Paper>
    );
  }

  return (
    <>
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: "#f3f4f6" }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 600, color: "#1f2937" }}>
                Service Name
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#1f2937" }}>
                Type
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#1f2937" }}>
                Status
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#1f2937" }}>
                Last Updated
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontWeight: 600, color: "#1f2937" }}
              >
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {secrets.map((secret) => (
              <TableRow
                key={secret.name}
                sx={{ "&:hover": { bgcolor: "#f9fafb" } }}
              >
                <TableCell sx={{ fontWeight: 500, color: "#1f2937" }}>
                  {secret.name}
                </TableCell>
                <TableCell sx={{ color: "#6b7280" }}>{secret.type}</TableCell>
                <TableCell>
                  <Chip
                    icon={getStatusIcon(secret.status)}
                    label={getStatusLabel(secret.status)}
                    color={getStatusColor(secret.status) as any}
                    size="small"
                    variant="filled"
                  />
                </TableCell>
                <TableCell sx={{ color: "#6b7280" }}>
                  {formatDate(secret.lastUpdated)}
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    onClick={(e) => handleMenuOpen(e, secret.name)}
                    aria-label="actions"
                  >
                    <MoreVertical className="w-5 h-5" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem disabled>
          <Eye className="w-4 h-4 mr-2" />
          View Metadata
        </MenuItem>
        <MenuItem disabled>
          <Clock className="w-4 h-4 mr-2" />
          Rotate
        </MenuItem>
        <MenuItem
          onClick={() => handleDeleteClick(selectedSecret || "")}
          sx={{ color: "error.main" }}
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Delete
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={Boolean(deleteConfirm)}
        onClose={() => setDeleteConfirm(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600, color: "#1f2937" }}>
          Delete Secret?
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: "#6b7280", mt: 1 }}>
            Are you sure you want to delete <strong>{deleteConfirm}</strong>?
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button
            onClick={handleConfirmDelete}
            color="error"
            variant="contained"
            disabled={deleting}
          >
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

// Import Lock icon at component level
import { Lock } from "lucide-react";

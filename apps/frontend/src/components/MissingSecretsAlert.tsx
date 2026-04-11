/**
 * MissingSecretsAlert Component
 * Alerts for critical missing secrets
 */

import React, { useState, useEffect } from "react";
import { Alert, Button, Box, Collapse } from "@mui/material";
import { AlertCircle, X } from "lucide-react";

interface MissingSecretsAlertProps {
  missingSecrets: string[];
  onAddSecret?: (secretName: string) => void;
}

const CRITICAL_SECRETS = ["OPENAI_API_KEY", "GEMINI_API_KEY", "SHODAN_API_KEY"];

/**
 * MissingSecretsAlert Component
 */
export function MissingSecretsAlert({
  missingSecrets,
  onAddSecret,
}: MissingSecretsAlertProps) {
  const [dismissed, setDismissed] = useState(false);
  const [show, setShow] = useState(false);

  // Check localStorage for dismissed state
  useEffect(() => {
    const isDismissed = localStorage.getItem("vault-missing-secrets-dismissed");
    setDismissed(isDismissed === "true");
  }, []);

  // Show alert if there are missing critical secrets
  useEffect(() => {
    const hasMissing = CRITICAL_SECRETS.some((secret) =>
      missingSecrets.includes(secret),
    );
    setShow(hasMissing && !dismissed);
  }, [missingSecrets, dismissed]);

  if (!show) {
    return null;
  }

  const criticalMissing = CRITICAL_SECRETS.filter((secret) =>
    missingSecrets.includes(secret),
  );

  const handleDismiss = () => {
    localStorage.setItem("vault-missing-secrets-dismissed", "true");
    setDismissed(true);
    setShow(false);
  };

  const handleAddSecret = (secretName: string) => {
    if (onAddSecret) {
      onAddSecret(secretName);
    }
  };

  return (
    <Collapse in={show}>
      <Alert
        severity="warning"
        sx={{
          mb: 3,
          bgcolor: "#fef3c7",
          borderColor: "#fcd34d",
          color: "#92400e",
          display: "flex",
          alignItems: "flex-start",
          gap: 2,
        }}
        icon={<AlertCircle className="w-5 h-5" />}
        action={
          <Button
            color="inherit"
            size="small"
            onClick={handleDismiss}
            sx={{ minWidth: "auto" }}
          >
            <X className="w-4 h-4" />
          </Button>
        }
      >
        <Box sx={{ flex: 1 }}>
          <Box sx={{ fontWeight: 600, mb: 1 }}>
            {criticalMissing.length} Critical Secret(s) Missing
          </Box>
          <Box sx={{ fontSize: "0.875rem", mb: 1 }}>
            Your setup is incomplete. These secrets are required for full
            functionality:
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 2 }}>
            {criticalMissing.map((secret) => (
              <Box
                key={secret}
                sx={{
                  bgcolor: "#fbbf24",
                  color: "#78350f",
                  px: 2,
                  py: 0.5,
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                }}
              >
                {secret}
              </Box>
            ))}
          </Box>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            {criticalMissing.map((secret) => (
              <Button
                key={secret}
                size="small"
                variant="contained"
                sx={{
                  bgcolor: "#d97706",
                  color: "white",
                  "&:hover": { bgcolor: "#b45309" },
                  textTransform: "none",
                  fontSize: "0.875rem",
                }}
                onClick={() => handleAddSecret(secret)}
              >
                Add {secret}
              </Button>
            ))}
          </Box>
        </Box>
      </Alert>
    </Collapse>
  );
}

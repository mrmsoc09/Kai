/**
 * AddSecretForm Component
 * Form for adding new secrets to Vault
 */

import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Box,
  CircularProgress,
  Alert,
  InputAdornment,
  IconButton,
} from "@mui/material";
import { Eye, EyeOff, Copy, CheckCircle } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import {
  StoreSecretRequest,
  ServiceType,
  EnvironmentTag,
} from "../types/vault";

interface AddSecretFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (request: StoreSecretRequest) => Promise<void>;
  onTest?: (service: ServiceType, value: string) => Promise<boolean>;
}

const SERVICE_TYPES: { value: ServiceType; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
  { value: "ollama", label: "Ollama" },
  { value: "shodan", label: "Shodan" },
  { value: "github", label: "GitHub" },
  { value: "aws", label: "AWS" },
  { value: "custom", label: "Custom" },
];

const DEFAULT_TYPES: Record<ServiceType, string> = {
  openai: "OPENAI_API_KEY",
  gemini: "GEMINI_API_KEY",
  ollama: "OLLAMA_BASE_URL",
  shodan: "SHODAN_API_KEY",
  github: "GITHUB_TOKEN",
  aws: "AWS_SECRET_ACCESS_KEY",
  custom: "CUSTOM_SECRET",
};

const ENVIRONMENT_OPTIONS: EnvironmentTag[] = [
  "production",
  "staging",
  "development",
];

/**
 * AddSecretForm Component
 */
export function AddSecretForm({
  open,
  onClose,
  onSubmit,
  onTest,
}: AddSecretFormProps) {
  const { control, watch, handleSubmit, reset, formState } =
    useForm<StoreSecretRequest>({
      defaultValues: {
        name: "",
        type: "CUSTOM_SECRET",
        value: "",
        description: "",
        environment: "production",
        tags: [],
      },
    });

  const [showValue, setShowValue] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const selectedService = watch("name") as ServiceType | undefined;
  const secretValue = watch("value");

  const handleServiceChange = (service: ServiceType) => {
    reset((prev) => ({
      ...prev,
      name: service,
      type: DEFAULT_TYPES[service],
    }));
  };

  const handleTest = async () => {
    if (!onTest || !selectedService || !secretValue) return;

    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(selectedService, secretValue);
      setTestResult(result);
    } catch (err) {
      setTestResult(false);
      setError(
        `Test failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setTesting(false);
    }
  };

  const handleSubmitForm = async (data: StoreSecretRequest) => {
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(data);
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save secret");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopyValue = () => {
    if (secretValue) {
      navigator.clipboard.writeText(secretValue);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, color: "#1f2937" }}>
        Add New Secret
      </DialogTitle>

      <DialogContent sx={{ pt: 2 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {/* Service Dropdown */}
          <FormControl fullWidth>
            <InputLabel>Service</InputLabel>
            <Select
              value={selectedService || ""}
              onChange={(e) =>
                handleServiceChange(e.target.value as ServiceType)
              }
              label="Service"
            >
              {SERVICE_TYPES.map((service) => (
                <MenuItem key={service.value} value={service.value}>
                  {service.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Secret Type Field */}
          <Controller
            name="type"
            control={control}
            rules={{ required: "Type is required" }}
            render={({ field, fieldState: { error: typeError } }) => (
              <TextField
                {...field}
                label="Secret Type"
                placeholder="e.g., OPENAI_API_KEY"
                fullWidth
                error={!!typeError}
                helperText={typeError?.message}
              />
            )}
          />

          {/* Secret Value Field */}
          <Controller
            name="value"
            control={control}
            rules={{ required: "Secret value is required" }}
            render={({ field, fieldState: { error: valueError } }) => (
              <TextField
                {...field}
                label="Secret Value"
                type={showValue ? "text" : "password"}
                fullWidth
                error={!!valueError}
                helperText={valueError?.message}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowValue(!showValue)}
                        size="small"
                        edge="end"
                      >
                        {showValue ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </IconButton>
                      {secretValue && (
                        <IconButton
                          onClick={handleCopyValue}
                          size="small"
                          edge="end"
                          color={copied ? "success" : "default"}
                        >
                          {copied ? (
                            <CheckCircle className="w-4 h-4" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </IconButton>
                      )}
                    </InputAdornment>
                  ),
                }}
              />
            )}
          />

          {/* Description Field */}
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Description (optional)"
                placeholder="What is this secret for?"
                multiline
                rows={2}
                fullWidth
              />
            )}
          />

          {/* Environment Tag */}
          <FormControl fullWidth>
            <InputLabel>Environment</InputLabel>
            <Controller
              name="environment"
              control={control}
              render={({ field }) => (
                <Select {...field} label="Environment">
                  {ENVIRONMENT_OPTIONS.map((env) => (
                    <MenuItem key={env} value={env}>
                      {env.charAt(0).toUpperCase() + env.slice(1)}
                    </MenuItem>
                  ))}
                </Select>
              )}
            />
          </FormControl>

          {/* Test Result */}
          {testResult !== null && (
            <Alert
              severity={testResult ? "success" : "error"}
              onClose={() => setTestResult(null)}
            >
              {testResult
                ? "Connection test successful!"
                : "Connection test failed. Please check the value."}
            </Alert>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        {onTest && selectedService && secretValue && (
          <Button
            onClick={handleTest}
            variant="outlined"
            disabled={testing || submitting}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
            }}
          >
            {testing && <CircularProgress size={16} />}
            Test Connection
          </Button>
        )}
        <Button
          onClick={handleSubmit(handleSubmitForm)}
          variant="contained"
          disabled={submitting || !selectedService || !formState.isValid}
        >
          {submitting ? (
            <>
              <CircularProgress size={16} sx={{ mr: 1 }} />
              Saving...
            </>
          ) : (
            "Save Secret"
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

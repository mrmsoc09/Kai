/**
 * Repair Pipeline Panel Component
 * Executes and visualizes the end-to-end vulnerability repair workflow
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  TextField,
  Alert,
  AlertTitle,
  LinearProgress,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Divider,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Code as CodeIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import {
  discoverAndRepair,
  getRepairPipelineHealth,
  type RepairPipelineResult,
  type RepairPipelineHealth,
} from '../../api/repair';

interface RepairPipelinePanelProps {
  defaultTarget?: string;
}

export const RepairPipelinePanel: React.FC<RepairPipelinePanelProps> = ({ defaultTarget = '' }) => {
  const [target, setTarget] = useState(defaultTarget);
  const [autoRepair, setAutoRepair] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RepairPipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<RepairPipelineHealth | null>(null);

  const steps = ['Discovery', 'Analysis', 'Repair', 'Validation', 'Report'];

  useEffect(() => {
    loadHealth();
  }, []);

  const loadHealth = async () => {
    try {
      const healthData = await getRepairPipelineHealth();
      setHealth(healthData);
    } catch (err: any) {
      console.error('Failed to load repair pipeline health:', err);
    }
  };

  const handleExecute = async () => {
    if (!target) {
      setError('Target is required');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const pipelineResult = await discoverAndRepair(target, autoRepair);
      setResult(pipelineResult);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to execute repair pipeline');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'error';
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      case 'low':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Vulnerability Repair Pipeline
      </Typography>
      <Typography variant="body2" color="textSecondary" paragraph>
        Automated end-to-end workflow: Discovery → Analysis → Repair → Validation → Report
      </Typography>

      {/* Health Status */}
      {health && (
        <Alert severity={health.ok ? 'success' : 'error'} sx={{ mb: 3 }}>
          <AlertTitle>Pipeline Status</AlertTitle>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
            <Chip
              label={`Claude Code: ${health.cli_tools.claude_code ? 'Available' : 'Not Available'}`}
              color={health.cli_tools.claude_code ? 'success' : 'default'}
              size="small"
            />
            <Chip
              label={`Codex: ${health.cli_tools.codex ? 'Available' : 'Not Available'}`}
              color={health.cli_tools.codex ? 'success' : 'default'}
              size="small"
            />
            <Chip
              label={`Gemini: ${health.cli_tools.gemini ? 'Available' : 'Not Available'}`}
              color={health.cli_tools.gemini ? 'success' : 'default'}
              size="small"
            />
          </Box>
        </Alert>
      )}

      {/* Configuration */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Configuration
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                label="Target"
                placeholder="example.com or 192.168.1.1"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                disabled={loading}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={
                  <Switch
                    checked={autoRepair}
                    onChange={(e) => setAutoRepair(e.target.checked)}
                    disabled={loading}
                  />
                }
                label="Auto-Apply Repairs"
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<PlayIcon />}
                onClick={handleExecute}
                disabled={loading || !target}
                fullWidth
              >
                {loading ? 'Executing Pipeline...' : 'Execute Repair Pipeline'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Loading State */}
      {loading && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Stepper activeStep={-1} alternativeLabel>
              {steps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
            <Box sx={{ mt: 2 }}>
              <LinearProgress />
              <Typography variant="body2" align="center" sx={{ mt: 1 }}>
                Pipeline in progress...
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Error State */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <AlertTitle>Pipeline Error</AlertTitle>
          {error}
        </Alert>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Vulnerabilities Found
                  </Typography>
                  <Typography variant="h4">{result.vulnerabilities_found}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Repairs Generated
                  </Typography>
                  <Typography variant="h4">{result.repairs_generated}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Repairs Applied
                  </Typography>
                  <Typography variant="h4" color="success.main">
                    {result.repairs_applied}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Total Cost
                  </Typography>
                  <Typography variant="h4">{formatCurrency(result.total_cost_cents)}</Typography>
                  <Typography variant="caption" color="textSecondary">
                    {result.local_percentage.toFixed(1)}% local / {result.paid_percentage.toFixed(1)}% paid
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Cost Breakdown */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Cost Breakdown
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Phase</TableCell>
                      <TableCell align="right">Cost</TableCell>
                      <TableCell>Model Type</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>Discovery</TableCell>
                      <TableCell align="right">{formatCurrency(result.post_review_report.cost_breakdown.discovery_cost)}</TableCell>
                      <TableCell>
                        <Chip label="LOCAL" size="small" color="success" />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Analysis</TableCell>
                      <TableCell align="right">{formatCurrency(result.post_review_report.cost_breakdown.analysis_cost)}</TableCell>
                      <TableCell>
                        <Chip label="HYBRID" size="small" color="warning" />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Repair</TableCell>
                      <TableCell align="right">{formatCurrency(result.post_review_report.cost_breakdown.repair_cost)}</TableCell>
                      <TableCell>
                        <Chip label="PAID API" size="small" color="error" />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Validation</TableCell>
                      <TableCell align="right">{formatCurrency(result.post_review_report.cost_breakdown.validation_cost)}</TableCell>
                      <TableCell>
                        <Chip label="LOCAL" size="small" color="success" />
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          {/* Changes Applied */}
          {result.post_review_report.changes.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <SecurityIcon sx={{ mr: 1 }} />
                  Changes Applied
                </Typography>
                {result.post_review_report.changes.map((change, index) => (
                  <Accordion key={index}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                        <Chip
                          label={change.severity}
                          color={getSeverityColor(change.severity) as any}
                          size="small"
                        />
                        <Typography>{change.file}</Typography>
                        <Typography variant="body2" color="textSecondary">
                          {change.vulnerability}
                        </Typography>
                        {change.validation.is_valid && (
                          <CheckCircleIcon color="success" sx={{ ml: 'auto' }} />
                        )}
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Grid container spacing={2}>
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle2" gutterBottom>
                            Before (Vulnerable)
                          </Typography>
                          <Paper sx={{ p: 2, bgcolor: '#fee', maxHeight: 300, overflow: 'auto' }}>
                            <pre style={{ margin: 0, fontSize: '0.85rem' }}>{change.before_code}</pre>
                          </Paper>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Typography variant="subtitle2" gutterBottom>
                            After (Fixed)
                          </Typography>
                          <Paper sx={{ p: 2, bgcolor: '#efe', maxHeight: 300, overflow: 'auto' }}>
                            <pre style={{ margin: 0, fontSize: '0.85rem' }}>{change.after_code}</pre>
                          </Paper>
                        </Grid>
                        <Grid item xs={12}>
                          <Divider sx={{ my: 1 }} />
                          <Typography variant="subtitle2" gutterBottom>
                            Validation
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                            <Chip
                              label={change.validation.is_valid ? 'Valid' : 'Invalid'}
                              color={change.validation.is_valid ? 'success' : 'error'}
                              size="small"
                            />
                            <Typography variant="body2">
                              Confidence: {(change.validation.confidence * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                          {change.validation.issues.length > 0 && (
                            <Alert severity="warning" sx={{ mt: 1 }}>
                              Issues: {change.validation.issues.join(', ')}
                            </Alert>
                          )}
                          <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                            Rollback: <code>{change.rollback_command}</code>
                          </Typography>
                        </Grid>
                      </Grid>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Next Steps */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Next Steps
              </Typography>
              <Box component="ul" sx={{ pl: 2 }}>
                {result.post_review_report.next_steps.map((step, index) => (
                  <Typography component="li" key={index} variant="body2" sx={{ mb: 1 }}>
                    {step}
                  </Typography>
                ))}
              </Box>
            </CardContent>
          </Card>
        </>
      )}
    </Box>
  );
};

export default RepairPipelinePanel;

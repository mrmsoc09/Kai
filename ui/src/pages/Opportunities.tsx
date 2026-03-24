import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { opportunityService, workflowService } from '../api';
import { ActionModal } from '../components/ActionModal';
import { ChainSummaryPanel } from '../components/ChainSummaryPanel';
import { DecisionSummaryPanel } from '../components/DecisionSummaryPanel';
import type { Opportunity, OpportunityActionCapabilities, ScanQueueSettings } from '../types';
import { formatConfidence } from '../utils/format';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import { extractRealtimeMissionEvent } from '../lib/realtime/missionEventReducer';

const defaultActionCapabilities: OpportunityActionCapabilities = {
  approve: false,
  reject: false,
  execute: false,
  reason: 'Opportunity action workflow unavailable.',
  requires_role: 'analyst',
};

const asPercent = (value: number | undefined): string => `${Math.round((value ?? 0) * 100)}%`;
const SCAN_QUEUE_ITEMS_STORAGE_KEY = 'kai.scan_queue_items_v1';
const SCAN_CONCURRENCY_LOWER_BOUND = 1;
const SCAN_CONCURRENCY_UPPER_BOUND = 20;

interface ScanQueueItem {
  opportunityId: string;
  queuedAt: string;
  reason: string;
}

interface ActionRunOptions {
  bypassQueueLimit?: boolean;
}

type ActionRunResult = 'success' | 'queued' | 'failed';

const defaultScanQueueSettings: ScanQueueSettings = {
  minConcurrent: 1,
  maxConcurrent: 3,
};

const clampScanConcurrency = (value: number): number => {
  if (!Number.isFinite(value)) {
    return SCAN_CONCURRENCY_LOWER_BOUND;
  }
  return Math.max(SCAN_CONCURRENCY_LOWER_BOUND, Math.min(SCAN_CONCURRENCY_UPPER_BOUND, Math.floor(value)));
};

const normalizeQueueSettings = (value: Partial<ScanQueueSettings>): ScanQueueSettings => {
  const minConcurrent = clampScanConcurrency(value.minConcurrent ?? defaultScanQueueSettings.minConcurrent);
  const maxConcurrent = clampScanConcurrency(value.maxConcurrent ?? defaultScanQueueSettings.maxConcurrent);
  if (minConcurrent > maxConcurrent) {
    return { minConcurrent: maxConcurrent, maxConcurrent };
  }
  return { minConcurrent, maxConcurrent };
};

const loadScanQueueItems = (): ScanQueueItem[] => {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(SCAN_QUEUE_ITEMS_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
      .map((row) => ({
        opportunityId: String(row.opportunityId ?? ''),
        queuedAt: String(row.queuedAt ?? ''),
        reason: String(row.reason ?? ''),
      }))
      .filter((row) => row.opportunityId.length > 0);
  } catch {
    return [];
  }
};

const getExecutionMetadata = (opportunity: Opportunity): Record<string, unknown> =>
  (opportunity.execution_metadata as Record<string, unknown> | undefined) ?? {};

const getExecutionFailureSummary = (opportunity: Opportunity): string | null => {
  if (String(opportunity.status ?? '') !== 'failed') {
    return null;
  }
  const metadata = getExecutionMetadata(opportunity);
  const lastError = typeof metadata.last_error === 'string' ? metadata.last_error : '';
  const blockedTargets = Array.isArray(metadata.blocked_targets)
    ? metadata.blocked_targets.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
    : [];

  if (lastError === 'no_executable_targets' && blockedTargets.length > 0) {
    const preview = blockedTargets
      .slice(0, 2)
      .map((row) => {
        const target = String(row.target ?? row.evaluated_target ?? 'target');
        const reason = String(row.reason ?? 'blocked');
        return `${target} (${reason})`;
      })
      .join(', ');
    const remainder = blockedTargets.length > 2 ? ` +${blockedTargets.length - 2} more` : '';
    return `No executable targets: ${preview}${remainder}`;
  }
  if (lastError) {
    return `Execution failed: ${lastError}`;
  }
  return blockedTargets.length > 0 ? 'Execution failed due to blocked targets.' : 'Execution failed.';
};

export function Opportunities() {
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<Opportunity[]>([]);
  const [search, setSearch] = useState(searchParams.get('search') ?? '');
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [actionCapabilities, setActionCapabilities] = useState<OpportunityActionCapabilities>(defaultActionCapabilities);
  const [reviewTargetsByOpportunity, setReviewTargetsByOpportunity] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingActionKey, setPendingActionKey] = useState<string | null>(null);
  const [modal, setModal] = useState<{
    action: 'approve' | 'reject' | 'execute';
    opportunity: Opportunity;
  } | null>(null);
  const [intakeModalOpportunity, setIntakeModalOpportunity] = useState<Opportunity | null>(null);
  const [intakeForm, setIntakeForm] = useState({
    objective: '',
    targetFocus: '',
    desiredOutcome: '',
    constraints: '',
    notes: '',
  });
  const [intakeSubmitting, setIntakeSubmitting] = useState(false);
  const [intakeFeedback, setIntakeFeedback] = useState<string | null>(null);
  const [scanQueueSettings, setScanQueueSettings] = useState<ScanQueueSettings>(defaultScanQueueSettings);
  const [scanQueue, setScanQueue] = useState<ScanQueueItem[]>(() => loadScanQueueItems());
  const [scanQueueDraft, setScanQueueDraft] = useState(() => ({
    minConcurrent: String(defaultScanQueueSettings.minConcurrent),
    maxConcurrent: String(defaultScanQueueSettings.maxConcurrent),
  }));
  const [scanQueueDispatching, setScanQueueDispatching] = useState(false);
  const [scanQueueFeedback, setScanQueueFeedback] = useState<string | null>(null);
  const { permissions } = useAuth();
  const webSocketState = useAppStore((state) => state.webSocketState);
  const refreshTimerRef = useRef<number | null>(null);
  const opportunitiesById = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);
  const queuedOpportunityIds = useMemo(() => new Set(scanQueue.map((row) => row.opportunityId)), [scanQueue]);
  const runningScanCount = useMemo(() => rows.filter((row) => row.status === 'executing').length, [rows]);
  const queuedScanEntries = useMemo(
    () => scanQueue.map((row) => ({ ...row, opportunity: opportunitiesById.get(row.opportunityId) ?? null })),
    [opportunitiesById, scanQueue],
  );

  const mergeOpportunity = useCallback((updated: Opportunity) => {
    setRows((previous) => previous.map((row) => (row.id === updated.id ? updated : row)));
    setSelectedOpportunity((previous) => (previous && previous.id === updated.id ? updated : previous));
  }, []);

  const hydrateReviewTargets = useCallback((opportunity: Opportunity) => {
    const reviewed = opportunity.approved_targets && opportunity.approved_targets.length > 0
      ? opportunity.approved_targets
      : opportunity.candidate_targets ?? [];
    setReviewTargetsByOpportunity((previous) => ({
      ...previous,
      [opportunity.id]: reviewed,
    }));
  }, []);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const payload = await opportunityService.list({
        search: search || undefined,
        sort_by: 'score',
        limit: 200,
      });
      setRows(payload.opportunities);
      setReviewTargetsByOpportunity((previous) => {
        const next = { ...previous };
        for (const row of payload.opportunities) {
          if (!next[row.id]) {
            next[row.id] = row.approved_targets && row.approved_targets.length > 0
              ? row.approved_targets
              : row.candidate_targets ?? [];
          }
        }
        return next;
      });

      if (payload.opportunities.length > 0) {
        setSelectedOpportunity((current) => {
          if (current && payload.opportunities.some((row) => row.id === current.id)) {
            return current;
          }
          return payload.opportunities[0];
        });
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to load opportunities.');
    } finally {
      setLoading(false);
    }
  }, [search]);

  const scheduleRealtimeRefresh = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      void loadOpportunities();
    }, 300);
  }, [loadOpportunities]);

  const { connect, disconnect, subscribe, unsubscribe } = useWebSocket<unknown>({
    path: appConfig.missionEventsPath,
    onMessage: (message) => {
      const event = extractRealtimeMissionEvent(message);
      if (!event || !event.event_type.startsWith('opportunity_')) {
        return;
      }
      scheduleRealtimeRefresh();
    },
  });

  useEffect(() => {
    const loadCapabilities = async () => {
      try {
        const capabilities = await opportunityService.getActionCapabilities();
        setActionCapabilities(capabilities);
      } catch {
        setActionCapabilities(defaultActionCapabilities);
      }
    };

    void loadOpportunities();
    void loadCapabilities();
  }, [loadOpportunities]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadOpportunities();
    }, 250);
    return () => window.clearTimeout(id);
  }, [loadOpportunities, search]);

  useEffect(() => {
    connect();
    return () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      disconnect();
    };
  }, [connect, disconnect]);

  useEffect(() => {
    if (webSocketState === 'connected') {
      subscribe('mission_events');
      return () => {
        unsubscribe('mission_events');
      };
    }
    return undefined;
  }, [subscribe, unsubscribe, webSocketState]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(SCAN_QUEUE_ITEMS_STORAGE_KEY, JSON.stringify(scanQueue));
  }, [scanQueue]);

  useEffect(() => {
    setScanQueueDraft({
      minConcurrent: String(scanQueueSettings.minConcurrent),
      maxConcurrent: String(scanQueueSettings.maxConcurrent),
    });
  }, [scanQueueSettings.maxConcurrent, scanQueueSettings.minConcurrent]);

  useEffect(() => {
    let isCancelled = false;

    const loadPersistedScanQueueSettings = async () => {
      try {
        const settings = await opportunityService.getScanQueueSettings();
        if (isCancelled) {
          return;
        }
        setScanQueueSettings(normalizeQueueSettings(settings));
      } catch {
        if (isCancelled) {
          return;
        }
        setScanQueueSettings(defaultScanQueueSettings);
      }
    };

    void loadPersistedScanQueueSettings();
    return () => {
      isCancelled = true;
    };
  }, []);

  const setTargetReviewed = useCallback((opportunityId: string, target: string, selected: boolean) => {
    setReviewTargetsByOpportunity((previous) => {
      const current = new Set(previous[opportunityId] ?? []);
      if (selected) {
        current.add(target);
      } else {
        current.delete(target);
      }
      return { ...previous, [opportunityId]: Array.from(current) };
    });
  }, []);

  const applyBatchSelection = useCallback((opportunity: Opportunity, batchId: string) => {
    const batch = (opportunity.target_batches ?? []).find((row) => row.batch_id === batchId);
    if (!batch) {
      return;
    }
    setReviewTargetsByOpportunity((previous) => ({ ...previous, [opportunity.id]: batch.targets }));
  }, []);

  const runExpand = useCallback(async (opportunity: Opportunity) => {
    setError(null);
    setPendingActionKey(`expand:${opportunity.id}`);
    try {
      const updated = await opportunityService.expand(opportunity.id, {
        vuln_type: opportunity.vuln_types[0] ?? undefined,
      });
      mergeOpportunity(updated);
      hydrateReviewTargets(updated);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Unable to expand opportunity.');
    } finally {
      setPendingActionKey(null);
    }
  }, [hydrateReviewTargets, mergeOpportunity]);

  const openModal = useCallback((opportunity: Opportunity, action: 'approve' | 'reject' | 'execute') => {
    setModal({ action, opportunity });
  }, []);

  const closeModal = useCallback(() => setModal(null), []);

  const openIntakeModal = useCallback((opportunity: Opportunity) => {
    setIntakeModalOpportunity(opportunity);
    setIntakeForm({
      objective: '',
      targetFocus: '',
      desiredOutcome: '',
      constraints: '',
      notes: '',
    });
    setIntakeFeedback(null);
  }, []);

  const closeIntakeModal = useCallback(() => {
    if (intakeSubmitting) {
      return;
    }
    setIntakeModalOpportunity(null);
  }, [intakeSubmitting]);

  const submitIntake = useCallback(async () => {
    if (!intakeModalOpportunity || intakeSubmitting) {
      return;
    }

    setIntakeSubmitting(true);
    setError(null);
    setIntakeFeedback(null);

    const noteLines = [
      intakeForm.objective ? `Operator objective: ${intakeForm.objective}` : '',
      intakeForm.targetFocus ? `Target focus: ${intakeForm.targetFocus}` : '',
      intakeForm.desiredOutcome ? `Desired outcome: ${intakeForm.desiredOutcome}` : '',
      intakeForm.constraints ? `Execution constraints: ${intakeForm.constraints}` : '',
      intakeForm.notes ? `Additional notes: ${intakeForm.notes}` : '',
    ].filter((row) => row.length > 0);

    try {
      const workflow = await workflowService.create({
        opportunity_id: intakeModalOpportunity.id,
        notes: noteLines.join('\n'),
      });
      setIntakeModalOpportunity(null);
      setIntakeFeedback(`Workflow created: ${String(workflow.id ?? workflow.workflow_id ?? 'created')}`);
    } catch (intakeError) {
      const message = intakeError instanceof Error ? intakeError.message : 'Unable to submit opportunity intake.';
      setError(message);
    } finally {
      setIntakeSubmitting(false);
    }
  }, [intakeForm, intakeModalOpportunity, intakeSubmitting]);

  const enqueueScan = useCallback((opportunity: Opportunity, reason: string) => {
    setScanQueue((previous) => {
      if (previous.some((row) => row.opportunityId === opportunity.id)) {
        return previous;
      }
      return [
        ...previous,
        {
          opportunityId: opportunity.id,
          queuedAt: new Date().toISOString(),
          reason: reason.trim() || 'Queued by operator.',
        },
      ];
    });
    setScanQueueFeedback(`Queued scan for ${opportunity.name}.`);
  }, []);

  const removeQueuedScan = useCallback((opportunityId: string) => {
    setScanQueue((previous) => previous.filter((row) => row.opportunityId !== opportunityId));
  }, []);

  const applyScanQueueSettings = useCallback(async () => {
    setError(null);
    const minParsed = Number.parseInt(scanQueueDraft.minConcurrent, 10);
    const maxParsed = Number.parseInt(scanQueueDraft.maxConcurrent, 10);
    const nextSettings = normalizeQueueSettings({
      minConcurrent: Number.isNaN(minParsed) ? defaultScanQueueSettings.minConcurrent : minParsed,
      maxConcurrent: Number.isNaN(maxParsed) ? defaultScanQueueSettings.maxConcurrent : maxParsed,
    });
    try {
      const persisted = await opportunityService.setScanQueueSettings(nextSettings);
      const normalized = normalizeQueueSettings(persisted);
      setScanQueueSettings(normalized);
      setScanQueueFeedback(`Queue limits updated: min ${normalized.minConcurrent}, max ${normalized.maxConcurrent}.`);
    } catch (settingsError) {
      setError(settingsError instanceof Error ? settingsError.message : 'Unable to update scan queue settings.');
    }
  }, [scanQueueDraft.maxConcurrent, scanQueueDraft.minConcurrent]);

  const runAction = useCallback(
    async (
      opportunity: Opportunity,
      action: 'approve' | 'reject' | 'execute',
      reason: string,
      options: ActionRunOptions = {},
    ): Promise<ActionRunResult> => {
      setError(null);
      setPendingActionKey(`${action}:${opportunity.id}`);
      setModal(null);
      try {
        if (action === 'approve') {
          const reviewedTargets = reviewTargetsByOpportunity[opportunity.id] ?? [];
          const hasExpansionCandidates = (opportunity.expansion_candidates?.length ?? 0) > 0;
          const updated = await opportunityService.approve(opportunity.id, {
            reason: reason || undefined,
            approved_targets: hasExpansionCandidates && reviewedTargets.length > 0 ? reviewedTargets : undefined,
          });
          mergeOpportunity(updated);
          hydrateReviewTargets(updated);
          return 'success';
        }

        if (action === 'reject') {
          const updated = await opportunityService.reject(opportunity.id, { reason: reason || undefined });
          mergeOpportunity(updated);
          return 'success';
        }

        if (!options.bypassQueueLimit && runningScanCount >= scanQueueSettings.maxConcurrent) {
          enqueueScan(
            opportunity,
            reason || `Queued automatically because ${scanQueueSettings.maxConcurrent} scan(s) are already running.`,
          );
          return 'queued';
        }

        const updated = await opportunityService.execute(opportunity.id, { reason: reason || undefined });
        mergeOpportunity(updated);
        setScanQueueFeedback(`Started scan for ${opportunity.name}.`);
        return 'success';
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : `Unable to ${action} opportunity.`);
        return 'failed';
      } finally {
        setPendingActionKey(null);
      }
    },
    [
      enqueueScan,
      hydrateReviewTargets,
      mergeOpportunity,
      reviewTargetsByOpportunity,
      runningScanCount,
      scanQueueSettings.maxConcurrent,
    ],
  );

  const actionBlockedByRole = useMemo(
    () => !permissions.canOperateMissions && !permissions.canDecideGovernance,
    [permissions.canDecideGovernance, permissions.canOperateMissions],
  );

  const canExpandRow = (row: Opportunity): boolean => row.status !== 'executing' && !actionBlockedByRole;
  const canApproveRow = (row: Opportunity): boolean =>
    actionCapabilities.approve && row.approval_state !== 'approved' && row.status !== 'executing' && !actionBlockedByRole;
  const canRejectRow = (row: Opportunity): boolean =>
    actionCapabilities.reject && row.status !== 'executing' && row.status !== 'completed' && !actionBlockedByRole;
  const canExecuteRow = (row: Opportunity): boolean =>
    actionCapabilities.execute && row.approval_state === 'approved' && row.status !== 'executing' && !actionBlockedByRole;

  const dispatchQueuedScans = useCallback(async () => {
    if (scanQueueDispatching || scanQueue.length === 0 || actionBlockedByRole || !actionCapabilities.execute) {
      return;
    }

    let availableSlots = scanQueueSettings.maxConcurrent - runningScanCount;
    if (availableSlots <= 0) {
      return;
    }

    setScanQueueDispatching(true);
    try {
      for (const queuedItem of scanQueue) {
        if (availableSlots <= 0) {
          break;
        }
        const opportunity = opportunitiesById.get(queuedItem.opportunityId);
        if (!opportunity) {
          removeQueuedScan(queuedItem.opportunityId);
          continue;
        }
        const executable =
          actionCapabilities.execute &&
          opportunity.approval_state === 'approved' &&
          opportunity.status !== 'executing' &&
          !actionBlockedByRole;
        if (!executable) {
          const shouldDrop =
            opportunity.status === 'completed' ||
            opportunity.status === 'rejected' ||
            opportunity.approval_state !== 'approved';
          if (shouldDrop) {
            removeQueuedScan(queuedItem.opportunityId);
          }
          continue;
        }

        const result = await runAction(opportunity, 'execute', queuedItem.reason, { bypassQueueLimit: true });
        if (result === 'success') {
          removeQueuedScan(queuedItem.opportunityId);
          availableSlots -= 1;
          continue;
        }
        if (result === 'failed') {
          break;
        }
      }
    } finally {
      setScanQueueDispatching(false);
    }
  }, [
    actionBlockedByRole,
    actionCapabilities.execute,
    opportunitiesById,
    removeQueuedScan,
    runAction,
    runningScanCount,
    scanQueue,
    scanQueueDispatching,
    scanQueueSettings.maxConcurrent,
  ]);

  useEffect(() => {
    if (scanQueueDispatching || scanQueue.length === 0) {
      return;
    }
    if (actionBlockedByRole || !actionCapabilities.execute) {
      return;
    }
    if (runningScanCount >= scanQueueSettings.maxConcurrent) {
      return;
    }
    void dispatchQueuedScans();
  }, [
    actionBlockedByRole,
    actionCapabilities.execute,
    dispatchQueuedScans,
    runningScanCount,
    scanQueue.length,
    scanQueueDispatching,
    scanQueueSettings.maxConcurrent,
  ]);

  const selectedReviewTargets = selectedOpportunity ? (reviewTargetsByOpportunity[selectedOpportunity.id] ?? []) : [];
  const selectedIsQueued = selectedOpportunity ? queuedOpportunityIds.has(selectedOpportunity.id) : false;
  const selectedMetadata = selectedOpportunity ? getExecutionMetadata(selectedOpportunity) : {};
  const selectedMissionIds = Array.isArray(selectedMetadata.mission_ids) ? selectedMetadata.mission_ids.filter((row): row is string => typeof row === 'string') : [];
  const selectedReportIds = Array.isArray(selectedMetadata.report_ids) ? selectedMetadata.report_ids.filter((row): row is string => typeof row === 'string') : [];
  const selectedExecutionError = typeof selectedMetadata.last_error === 'string' ? selectedMetadata.last_error : '';
  const selectedBlockedTargets = Array.isArray(selectedMetadata.blocked_targets)
    ? selectedMetadata.blocked_targets.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
    : [];

  const rowStatusClass = (status: string | undefined): string => {
    switch (status) {
      case 'approved': return 'bg-emerald-500/5';
      case 'executing': return 'bg-cyan-500/5';
      case 'completed': return 'bg-slate-800/20';
      case 'rejected': return 'bg-rose-500/5 opacity-60';
      default: return '';
    }
  };

  const modalConfig = modal
    ? {
        approve: {
          title: 'Approve Opportunity',
          message: `Approve "${modal.opportunity.name}" for execution? Selected targets will be included.`,
          confirmLabel: 'Approve',
          confirmClass: 'bg-emerald-500/20 text-emerald-200 border-emerald-600/40 hover:bg-emerald-500/30',
          reasonPlaceholder: 'Approval rationale (optional)...',
        },
        reject: {
          title: 'Reject Opportunity',
          message: `Reject "${modal.opportunity.name}"? This removes it from the active queue.`,
          confirmLabel: 'Reject',
          confirmClass: 'bg-rose-500/20 text-rose-200 border-rose-600/40 hover:bg-rose-500/30',
          reasonPlaceholder: 'Rejection reason (optional)...',
        },
        execute: {
          title: 'Start Scan',
          message: `Start scan for "${modal.opportunity.name}"? This launches governed missions against approved targets.`,
          confirmLabel: 'Start Scan',
          confirmClass: 'bg-cyan-500/20 text-cyan-200 border-cyan-600/40 hover:bg-cyan-500/30',
          reasonPlaceholder: 'Scan note (optional)...',
        },
      }[modal.action]
    : null;

  return (
    <>
    {modal && modalConfig ? (
      <ActionModal
        isOpen
        title={modalConfig.title}
        message={modalConfig.message}
        requiresReason
        reasonPlaceholder={modalConfig.reasonPlaceholder}
        confirmLabel={modalConfig.confirmLabel}
        confirmClass={modalConfig.confirmClass}
        onConfirm={(reason) => void runAction(modal.opportunity, modal.action, reason)}
        onCancel={closeModal}
      />
    ) : null}
    {intakeModalOpportunity ? (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
        <div className="w-full max-w-xl rounded-lg border border-slate-700 bg-slate-900 p-4">
          <h3 className="text-sm font-semibold text-slate-100">Opportunity Intake</h3>
          <p className="mt-1 text-xs text-slate-400">Answer intake questions for <span className="text-cyan-200">{intakeModalOpportunity.name}</span>.</p>

          <div className="mt-3 space-y-2">
            <label className="block text-xs text-slate-300">
              1. What is your objective for this opportunity?
              <input
                value={intakeForm.objective}
                onChange={(event) => setIntakeForm((previous) => ({ ...previous, objective: event.target.value }))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="Validate XSS surface and collect report-grade evidence."
              />
            </label>
            <label className="block text-xs text-slate-300">
              2. Which targets or areas should be prioritized?
              <input
                value={intakeForm.targetFocus}
                onChange={(event) => setIntakeForm((previous) => ({ ...previous, targetFocus: event.target.value }))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="auth endpoints, public web app, API gateway"
              />
            </label>
            <label className="block text-xs text-slate-300">
              3. What outcome should this run produce?
              <input
                value={intakeForm.desiredOutcome}
                onChange={(event) => setIntakeForm((previous) => ({ ...previous, desiredOutcome: event.target.value }))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="One high-confidence finding with reproducible proof."
              />
            </label>
            <label className="block text-xs text-slate-300">
              4. Any constraints, exclusions, or timing notes?
              <input
                value={intakeForm.constraints}
                onChange={(event) => setIntakeForm((previous) => ({ ...previous, constraints: event.target.value }))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="Avoid login-required endpoints during this run."
              />
            </label>
            <label className="block text-xs text-slate-300">
              Notes
              <textarea
                value={intakeForm.notes}
                onChange={(event) => setIntakeForm((previous) => ({ ...previous, notes: event.target.value }))}
                className="mt-1 min-h-[5rem] w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="Additional operator context"
              />
            </label>
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={closeIntakeModal}
              className="rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-300"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void submitIntake()}
              disabled={intakeSubmitting}
              className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-50"
            >
              {intakeSubmitting ? 'Submitting…' : 'Create Workflow'}
            </button>
          </div>
        </div>
      </div>
    ) : null}
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Opportunity Workbench</h2>
          <p className="text-xs text-slate-400">Primary money screen: expand, review, approve, execute, and pivot to reports.</p>
        </div>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search opportunities, org, id..."
          className="w-80 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
        />
      </div>

      <section className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Scan Queue</h3>
            <p className="text-xs text-slate-400">
              running {runningScanCount} · queued {scanQueue.length} · limits min {scanQueueSettings.minConcurrent} / max {scanQueueSettings.maxConcurrent}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void dispatchQueuedScans()}
            disabled={scanQueueDispatching || scanQueue.length === 0 || runningScanCount >= scanQueueSettings.maxConcurrent}
            className="rounded border border-cyan-600/40 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200 disabled:opacity-50"
          >
            {scanQueueDispatching ? 'Dispatching…' : 'Dispatch Queued Scans'}
          </button>
        </div>

        <div className="grid gap-2 md:grid-cols-6">
          <label className="text-xs text-slate-300">
            Min Concurrent
            <input
              type="number"
              min={SCAN_CONCURRENCY_LOWER_BOUND}
              max={SCAN_CONCURRENCY_UPPER_BOUND}
              value={scanQueueDraft.minConcurrent}
              onChange={(event) => setScanQueueDraft((previous) => ({ ...previous, minConcurrent: event.target.value }))}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100"
            />
          </label>
          <label className="text-xs text-slate-300">
            Max Concurrent
            <input
              type="number"
              min={SCAN_CONCURRENCY_LOWER_BOUND}
              max={SCAN_CONCURRENCY_UPPER_BOUND}
              value={scanQueueDraft.maxConcurrent}
              onChange={(event) => setScanQueueDraft((previous) => ({ ...previous, maxConcurrent: event.target.value }))}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100"
            />
          </label>
          <div className="md:col-span-4 md:self-end">
            <button
              type="button"
              onClick={() => void applyScanQueueSettings()}
              className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:border-slate-500"
            >
              Apply Queue Limits
            </button>
          </div>
        </div>

        <p className="text-xs text-slate-400">
          {runningScanCount < scanQueueSettings.minConcurrent
            ? 'Running scans are below the configured minimum. Queued scans will auto-start when eligible.'
            : runningScanCount >= scanQueueSettings.maxConcurrent
              ? 'Queue is at max concurrency. New scans will be queued.'
              : 'Queue has available capacity for additional scans.'}
        </p>

        {queuedScanEntries.length === 0 ? (
          <p className="text-xs text-slate-500">No queued scans.</p>
        ) : (
          <div className="max-h-52 overflow-y-auto rounded border border-slate-800">
            <table className="min-w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-950 text-slate-400">
                <tr>
                  <th className="px-2 py-2">Opportunity</th>
                  <th className="px-2 py-2">Queued At</th>
                  <th className="px-2 py-2">Reason</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {queuedScanEntries.map((item) => (
                  <tr key={item.opportunityId}>
                    <td className="px-2 py-2 text-slate-100">
                      {item.opportunity ? item.opportunity.name : item.opportunityId}
                    </td>
                    <td className="px-2 py-2 text-slate-300">{new Date(item.queuedAt).toLocaleString()}</td>
                    <td className="px-2 py-2 text-slate-300">{item.reason || 'Queued by operator.'}</td>
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        onClick={() => removeQueuedScan(item.opportunityId)}
                        className="rounded border border-rose-600/40 px-2 py-1 text-xs text-rose-200 hover:border-rose-500/60"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              <th className="pb-2">Signal</th>
              <th className="pb-2">Confidence</th>
              <th className="pb-2">Yield</th>
              <th className="pb-2">Dup Risk</th>
              <th className="pb-2">Linked</th>
              <th className="pb-2">State</th>
              <th className="pb-2">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {rows.map((opportunity) => {
              const isQueued = queuedOpportunityIds.has(opportunity.id);
              return (
              <tr key={opportunity.id} className={rowStatusClass(String(opportunity.status ?? 'proposed'))}>
                <td className="py-3 text-slate-100">
                  <p>{opportunity.vuln_types[0] ?? 'unknown'} · {opportunity.organization}</p>
                  <div className="mt-1 flex flex-wrap gap-1 text-[10px] uppercase tracking-wide">
                    {(opportunity.confidence_score ?? 0) >= 0.75 ? <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">validated</span> : null}
                    {opportunity.chain_summary?.has_chain ? <span className="rounded border border-violet-500/30 bg-violet-500/10 px-1.5 py-0.5 text-violet-200">chain-backed</span> : null}
                    {(opportunity.linked_report_count ?? 0) > 0 ? <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-cyan-200">report-ready</span> : null}
                  </div>
                </td>
                <td className="py-3 text-slate-300">{formatConfidence(opportunity.confidence_score ?? opportunity.priority_score)}</td>
                <td className="py-3 text-slate-300">{(opportunity.expected_yield ?? opportunity.estimated_yield ?? 0).toFixed(2)}</td>
                <td className="py-3 text-slate-300">{asPercent(opportunity.duplicate_risk)}</td>
                <td className="py-3 text-slate-300">
                  <p>missions {opportunity.linked_mission_count ?? 0}</p>
                  <p>reports {opportunity.linked_report_count ?? 0}</p>
                </td>
                <td className="py-3">
                  <div className="space-y-1">
                    <p className="text-xs uppercase text-slate-200">{opportunity.status ?? 'proposed'}</p>
                    <p className="text-xs text-slate-500">approval: {opportunity.approval_state ?? 'pending'}</p>
                    {getExecutionFailureSummary(opportunity) ? (
                      <p className="max-w-xs text-xs text-rose-300">{getExecutionFailureSummary(opportunity)}</p>
                    ) : null}
                  </div>
                </td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedOpportunity(opportunity);
                        hydrateReviewTargets(opportunity);
                      }}
                      className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => openIntakeModal(opportunity)}
                      className="rounded border border-cyan-700/40 px-2 py-1 text-xs text-cyan-200 hover:border-cyan-500/60"
                    >
                      Intake
                    </button>
                    <button
                      type="button"
                      disabled={!canExpandRow(opportunity) || pendingActionKey === `expand:${opportunity.id}`}
                      onClick={() => void runExpand(opportunity)}
                      className={`rounded border px-2 py-1 text-xs ${
                        canExpandRow(opportunity) ? 'border-indigo-600/40 text-indigo-200' : 'border-slate-700 text-slate-500'
                      }`}
                    >
                      Expand
                    </button>
                    <button
                      type="button"
                      disabled={!canApproveRow(opportunity) || pendingActionKey === `approve:${opportunity.id}`}
                      onClick={() => openModal(opportunity, 'approve')}
                      title={actionCapabilities.approve ? 'Approve opportunity' : actionCapabilities.reason}
                      className={`rounded border px-2 py-1 text-xs ${
                        canApproveRow(opportunity) ? 'border-emerald-600/40 text-emerald-200' : 'border-slate-700 text-slate-500'
                      }`}
                    >
                      {pendingActionKey === `approve:${opportunity.id}` ? '…' : 'Approve'}
                    </button>
                    <button
                      type="button"
                      disabled={!canRejectRow(opportunity) || pendingActionKey === `reject:${opportunity.id}`}
                      onClick={() => openModal(opportunity, 'reject')}
                      title={actionCapabilities.reject ? 'Reject opportunity' : actionCapabilities.reason}
                      className={`rounded border px-2 py-1 text-xs ${
                        canRejectRow(opportunity) ? 'border-rose-600/40 text-rose-200' : 'border-slate-700 text-slate-500'
                      }`}
                    >
                      {pendingActionKey === `reject:${opportunity.id}` ? '…' : 'Reject'}
                    </button>
                    <button
                      type="button"
                      disabled={!canExecuteRow(opportunity) || pendingActionKey === `execute:${opportunity.id}`}
                      onClick={() => openModal(opportunity, 'execute')}
                      title={actionCapabilities.execute ? 'Start scan' : actionCapabilities.reason}
                      className={`rounded border px-2 py-1 text-xs ${
                        canExecuteRow(opportunity) ? 'border-cyan-600/40 text-cyan-200' : 'border-slate-700 text-slate-500'
                      }`}
                    >
                      {pendingActionKey === `execute:${opportunity.id}` ? 'Starting…' : 'Start Scan'}
                    </button>
                    <button
                      type="button"
                      disabled={!canExecuteRow(opportunity) || isQueued}
                      onClick={() => enqueueScan(opportunity, 'Queued manually by operator.')}
                      className={`rounded border px-2 py-1 text-xs ${
                        canExecuteRow(opportunity) && !isQueued ? 'border-amber-600/40 text-amber-200' : 'border-slate-700 text-slate-500'
                      }`}
                    >
                      {isQueued ? 'Queued' : 'Queue Scan'}
                    </button>
                  </div>
                </td>
              </tr>
            );
            })}
          </tbody>
        </table>
        {loading ? <p className="mt-3 text-xs text-slate-500">Loading opportunities...</p> : null}
        {!loading && rows.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">No opportunities for current filters. Expand a known signal or adjust search.</p>
        ) : null}
      </div>

      {selectedOpportunity ? (
        <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-100">{selectedOpportunity.name}</h3>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded border border-slate-700 px-2 py-1 text-slate-200">source: {selectedOpportunity.source_type ?? 'catalog_program'}</span>
              <span className="rounded border border-slate-700 px-2 py-1 text-slate-200">dup risk: {asPercent(selectedOpportunity.duplicate_risk)}</span>
              <Link to={`/reports?opportunity_id=${encodeURIComponent(selectedOpportunity.id)}`} className="rounded border border-violet-500/30 px-2 py-1 text-violet-200 hover:border-violet-400">
                linked reports
              </Link>
              {selectedMissionIds[0] ? (
                <Link to={`/mission-control?mission=${encodeURIComponent(selectedMissionIds[0])}`} className="rounded border border-cyan-500/30 px-2 py-1 text-cyan-200 hover:border-cyan-400">
                  linked mission
                </Link>
              ) : null}
              {selectedOpportunity.source_memory_id ? (
                <Link to={`/intelligence-center?memory_id=${encodeURIComponent(selectedOpportunity.source_memory_id)}`} className="rounded border border-slate-700 px-2 py-1 text-slate-300 hover:border-slate-500">
                  source memory
                </Link>
              ) : null}
            </div>
          </div>

          <dl className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <div className="flex justify-between gap-3"><dt className="text-slate-400">Expected Yield</dt><dd className="text-slate-100">{(selectedOpportunity.expected_yield ?? selectedOpportunity.estimated_yield ?? 0).toFixed(2)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-400">Expansion Score</dt><dd className="text-slate-100">{asPercent(selectedOpportunity.expansion_score)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-400">Linked Missions</dt><dd className="text-slate-100">{selectedOpportunity.linked_mission_count ?? selectedMissionIds.length}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-400">Linked Reports</dt><dd className="text-slate-100">{selectedOpportunity.linked_report_count ?? selectedReportIds.length}</dd></div>
          </dl>

          <DecisionSummaryPanel
            summary={selectedOpportunity.decision_summary ?? selectedOpportunity.expansion_rationale ?? null}
            detail={{
              chosen_action: selectedOpportunity.status,
              reason: selectedOpportunity.approval_reason ?? selectedOpportunity.rejection_reason ?? selectedOpportunity.expansion_rationale ?? '',
              score: selectedOpportunity.expansion_score ?? 0,
            }}
            title="Opportunity Decision Context"
          />

          <ChainSummaryPanel
            chain={null}
            summary={selectedOpportunity.chain_summary}
            title="Chain Context"
            emptyLabel="No chain context captured yet for this opportunity."
          />

          {(selectedOpportunity.target_batches ?? []).length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Expansion Batches</p>
              <div className="grid gap-2 md:grid-cols-2">
                {(selectedOpportunity.target_batches ?? []).map((batch) => (
                  <button
                    key={batch.batch_id}
                    type="button"
                    onClick={() => applyBatchSelection(selectedOpportunity, batch.batch_id)}
                    className="rounded border border-slate-700 bg-slate-950/40 px-3 py-2 text-left text-xs text-slate-200 hover:border-slate-500"
                  >
                    <p className="font-semibold">{batch.batch_id}</p>
                    <p>risk: {batch.risk_band} · targets: {batch.targets.length} · yield: {batch.expected_yield.toFixed(2)}</p>
                    <p className="text-slate-400">{batch.rationale}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {(selectedOpportunity.expansion_candidates ?? []).length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Target Review</p>
              <div className="max-h-64 overflow-y-auto rounded border border-slate-800">
                <table className="min-w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-950 text-slate-400">
                    <tr>
                      <th className="px-2 py-2">Include</th>
                      <th className="px-2 py-2">Target</th>
                      <th className="px-2 py-2">Similarity</th>
                      <th className="px-2 py-2">Expansion</th>
                      <th className="px-2 py-2">Dup Risk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {(selectedOpportunity.expansion_candidates ?? []).map((row) => {
                      const checked = selectedReviewTargets.includes(row.target);
                      return (
                        <tr key={row.target}>
                          <td className="px-2 py-2">
                            <input
                              checked={checked}
                              onChange={(event) => setTargetReviewed(selectedOpportunity.id, row.target, event.target.checked)}
                              type="checkbox"
                              className="h-4 w-4 accent-cyan-500"
                            />
                          </td>
                          <td className="px-2 py-2 text-slate-100">{row.target}</td>
                          <td className="px-2 py-2 text-slate-300">{asPercent(row.similarity_score)}</td>
                          <td className="px-2 py-2 text-slate-300">{asPercent(row.expansion_score)}</td>
                          <td className="px-2 py-2 text-slate-300">{asPercent(row.duplicate_risk)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-400">reviewed targets selected: {selectedReviewTargets.length}</p>
            </div>
          ) : null}

          <p className="text-xs text-slate-400">
            missions launched: {String(selectedMetadata.missions_launched ?? 0)} · missions completed: {String(selectedMetadata.missions_completed ?? 0)} · missions failed: {String(selectedMetadata.missions_failed ?? 0)}
          </p>
          {canExecuteRow(selectedOpportunity) ? (
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                disabled={pendingActionKey === `execute:${selectedOpportunity.id}`}
                onClick={() => openModal(selectedOpportunity, 'execute')}
                className="rounded border border-cyan-600/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
              >
                {pendingActionKey === `execute:${selectedOpportunity.id}` ? 'Starting…' : 'Start Scan'}
              </button>
              <button
                type="button"
                disabled={selectedIsQueued}
                onClick={() => enqueueScan(selectedOpportunity, 'Queued manually by operator.')}
                className="rounded border border-amber-600/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-200 disabled:opacity-50"
              >
                {selectedIsQueued ? 'Queued' : 'Queue Scan'}
              </button>
            </div>
          ) : null}
          {selectedExecutionError ? <p className="text-xs text-rose-300">execution error: {selectedExecutionError}</p> : null}
          {selectedBlockedTargets.length > 0 ? (
            <p className="text-xs text-amber-300">
              blocked targets: {selectedBlockedTargets.map((row) => `${String(row.target ?? row.evaluated_target ?? 'target')} (${String(row.reason ?? 'blocked')})`).join(', ')}
            </p>
          ) : null}
          {selectedOpportunity.approval_reason ? <p className="text-xs text-emerald-300">approval reason: {selectedOpportunity.approval_reason}</p> : null}
          {selectedOpportunity.rejection_reason ? <p className="text-xs text-rose-300">rejection reason: {selectedOpportunity.rejection_reason}</p> : null}
        </section>
      ) : null}

      {!actionCapabilities.approve || !actionCapabilities.reject || !actionCapabilities.execute ? (
        <p className="text-xs text-amber-300">
          Opportunity actions disabled: {actionCapabilities.reason} (required role: {actionCapabilities.requires_role}).
        </p>
      ) : null}

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      {intakeFeedback ? <p className="text-xs text-emerald-300">{intakeFeedback}</p> : null}
      {scanQueueFeedback ? <p className="text-xs text-cyan-300">{scanQueueFeedback}</p> : null}
    </section>
    </>
  );
}

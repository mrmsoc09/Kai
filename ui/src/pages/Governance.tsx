import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { governanceService } from '../api';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import { extractRealtimeMissionEvent } from '../lib/realtime/missionEventReducer';
import type { ApprovalDecision, ApprovalGate, ApprovalStatus } from '../types';
import { formatTimestamp } from '../utils/format';

const statusOptions: ApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED', 'CANCELED', 'DEFERRED', 'EXPIRED'];

const riskClass = (risk?: string | null): string => {
  if (!risk) {
    return 'unknown';
  }
  return risk.toLowerCase();
};

export function Governance() {
  const [approvals, setApprovals] = useState<ApprovalGate[]>([]);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus>('PENDING');
  const [error, setError] = useState<string | null>(null);
  const [pendingGateId, setPendingGateId] = useState<string | null>(null);
  const { permissions } = useAuth();
  const refreshTimerRef = useRef<number | null>(null);
  const webSocketState = useAppStore((state) => state.webSocketState);

  const loadApprovals = useCallback(async () => {
    setError(null);
    try {
      const data = await governanceService.list(statusFilter);
      setApprovals(data);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to load governance approvals.');
    }
  }, [statusFilter]);

  const scheduleRealtimeRefresh = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      void loadApprovals();
    }, 300);
  }, [loadApprovals]);

  const { connect, disconnect, subscribe, unsubscribe } = useWebSocket<unknown>({
    path: appConfig.missionEventsPath,
    onMessage: (message) => {
      const event = extractRealtimeMissionEvent(message);
      if (!event || event.category !== 'governance') {
        return;
      }
      scheduleRealtimeRefresh();
    },
  });

  useEffect(() => {
    void loadApprovals();
  }, [loadApprovals]);

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
      subscribe('governance_events');
      return () => {
        unsubscribe('governance_events');
      };
    }
    return undefined;
  }, [subscribe, unsubscribe, webSocketState]);

  useEffect(() => {
    if (webSocketState === 'connected') {
      return undefined;
    }
    const pollId = window.setInterval(() => {
      void loadApprovals();
    }, 10000);
    return () => window.clearInterval(pollId);
  }, [loadApprovals, webSocketState]);

  const handleDecision = async (approvalId: string, decision: ApprovalDecision) => {
    setError(null);
    setPendingGateId(approvalId);

    try {
      const notes = notesById[approvalId];
      if (decision === 'approve') {
        await governanceService.approve(approvalId, notes);
      } else if (decision === 'reject') {
        await governanceService.reject(approvalId, notes);
      } else {
        await governanceService.cancel(approvalId, notes);
      }

      await loadApprovals();
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : 'Unable to apply governance decision.');
    } finally {
      setPendingGateId(null);
    }
  };

  const canDecide = permissions.canDecideGovernance;
  const emptyMessage = useMemo(() => {
    if (statusFilter === 'PENDING') {
      return 'No pending governance actions.';
    }
    return `No ${statusFilter.toLowerCase()} approvals found.`;
  }, [statusFilter]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-100">Governance Console</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as ApprovalStatus)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void loadApprovals()}
            className="rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:border-slate-500"
          >
            Refresh
          </button>
        </div>
      </div>

      {!canDecide ? <p className="text-xs text-amber-300">Approve/reject actions require analyst or admin role.</p> : null}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      {approvals.length === 0 ? (
        <p className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-400">{emptyMessage}</p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {approvals.map((approval) => (
          <article key={approval.id} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-slate-100">{approval.campaign_id}</h3>
              <span className="rounded-full bg-slate-800 px-2 py-1 text-xs uppercase text-slate-300">{approval.status}</span>
            </div>
            <p className="text-sm text-slate-300">{approval.gate_reason}</p>
            <dl className="mt-3 space-y-1 text-xs text-slate-400">
              <div className="flex justify-between gap-3">
                <dt>Risk Band</dt>
                <dd className="text-slate-200">{riskClass(approval.risk_class)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Requested By</dt>
                <dd className="text-slate-200">{approval.requested_by}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Requested At</dt>
                <dd className="text-slate-200">{formatTimestamp(approval.requested_at)}</dd>
              </div>
              {approval.policy_basis ? (
                <div className="flex justify-between gap-3">
                  <dt>Policy Basis</dt>
                  <dd className="max-w-[70%] text-right text-slate-200">{approval.policy_basis}</dd>
                </div>
              ) : null}
            </dl>

            <textarea
              value={notesById[approval.id] ?? ''}
              onChange={(event) => setNotesById((previous) => ({ ...previous, [approval.id]: event.target.value }))}
              rows={3}
              placeholder="Operator notes"
              className="mt-3 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
            />

            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={!canDecide || pendingGateId === approval.id}
                onClick={() => void handleDecision(approval.id, 'approve')}
                className="rounded bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-200 disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={!canDecide || pendingGateId === approval.id}
                onClick={() => void handleDecision(approval.id, 'reject')}
                className="rounded bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-200 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                type="button"
                disabled={!canDecide || pendingGateId === approval.id}
                onClick={() => void handleDecision(approval.id, 'cancel')}
                className="rounded bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

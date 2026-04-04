/**
 * HiL Approvals Dashboard
 * Human-in-the-Loop approval workflow for email drafts and reports
 */

import React, { useEffect, useState } from 'react';
import DOMPurify from 'dompurify';
import {
  listPendingApprovals,
  getApproval,
  approveRequest,
  rejectRequest,
  getApprovalStats,
  ApprovalRequest,
  ApprovalListResponse,
  ApprovalStats
} from '../api/approvals';
import StatusChip from '../components/StatusChip';
import { useStore } from '../store/system';
import { toast } from '../store/toasts';

export default function ApprovalsDashboard() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [stats, setStats] = useState<ApprovalStats | null>(null);
  const [selected, setSelected] = useState<ApprovalRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const userId = useStore((s) => s.auth.user?.id) || 'user1';

  async function loadData() {
    setLoading(true);
    try {
      const [approvalsResp, statsResp] = await Promise.all([
        listPendingApprovals(),
        getApprovalStats()
      ]);
      setApprovals(approvalsResp.approvals);
      setStats(statsResp);
    } catch (e: any) {
      toast.error(`Error loading approvals: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => void loadData(), 30000);
    return () => clearInterval(interval);
  }, []);

  async function selectApproval(approval: ApprovalRequest) {
    setSelected(approval);
    // Load full details
    try {
      const full = await getApproval(approval.approval_id);
      setSelected(full);
    } catch (e: any) {
      console.error('Failed to load approval details:', e);
    }
  }

  async function handleApprove() {
    if (!selected) return;

    setActionInProgress(true);
    try {
      await approveRequest(selected.approval_id, userId, undefined);
      toast.success('Draft approved! You can now manually send the email.');
      setSelected(null);
      void loadData();
    } catch (e: any) {
      toast.error(`Failed to approve: ${e.message}`);
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleReject() {
    if (!selected) return;
    if (!rejectReason.trim()) {
      toast.warning('Please provide a rejection reason');
      return;
    }

    setActionInProgress(true);
    try {
      await rejectRequest(selected.approval_id, userId, rejectReason);
      toast.info('Draft rejected.');
      setSelected(null);
      setShowRejectModal(false);
      setRejectReason('');
      void loadData();
    } catch (e: any) {
      toast.error(`Failed to reject: ${e.message}`);
    } finally {
      setActionInProgress(false);
    }
  }

  function copyEmailToClipboard() {
    if (!selected?.content?.email_draft) return;

    const draft = selected.content.email_draft;
    const emailText = `To: ${draft.to}\nSubject: ${draft.subject}\n\n${draft.body}`;

    navigator.clipboard.writeText(emailText).then(() => {
      toast.success('Email copied to clipboard');
    }).catch(() => {
      toast.error('Failed to copy email to clipboard');
    });
  }

  const formatDate = (isoDate: string) => {
    return new Date(isoDate).toLocaleString();
  };

  const getSeverityColor = (type: string) => {
    if (type === 'report_submission') return '#D97706';
    if (type === 'email_reply') return '#3B82F6';
    return '#6B7280';
  };

  return (
    <div style={{
      padding: '24px',
      color: '#E5E7EB',
      background: '#0A0A0A',
      minHeight: '100vh'
    }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ color: '#355E3B', marginBottom: '8px', fontSize: '28px' }}>
          📋 HiL Approvals Dashboard
        </h1>
        <p style={{ color: '#9CA3AF', fontSize: '14px' }}>
          Review and approve email drafts before sending
        </p>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginBottom: '24px'
        }}>
          <StatCard label="Pending" value={stats.pending} color="#D97706" />
          <StatCard label="Approved" value={stats.approved} color="#10B981" />
          <StatCard label="Rejected" value={stats.rejected} color="#EF4444" />
          <StatCard label="Total Requests" value={stats.total_requests} color="#6B7280" />
        </div>
      )}

      {/* Main Content */}
      <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '24px' }}>
        {/* Approvals List */}
        <div style={{
          background: '#1A1A1A',
          border: '1px solid #2A2A2A',
          borderRadius: '8px',
          padding: '16px',
          maxHeight: '700px',
          overflowY: 'auto'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', color: '#355E3B' }}>
              Pending Approvals ({approvals.length})
            </h2>
            <button
              onClick={() => loadData()}
              style={{
                background: '#2A2A2A',
                border: '1px solid #355E3B',
                color: '#355E3B',
                padding: '4px 12px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              🔄 Refresh
            </button>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9CA3AF' }}>
              Loading...
            </div>
          ) : approvals.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9CA3AF' }}>
              ✅ No pending approvals
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {approvals.map(approval => (
                <div
                  key={approval.approval_id}
                  onClick={() => selectApproval(approval)}
                  style={{
                    background: selected?.approval_id === approval.approval_id ? '#2A2A2A' : '#111111',
                    border: selected?.approval_id === approval.approval_id ? '1px solid #355E3B' : '1px solid #1A1A1A',
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{
                      background: getSeverityColor(approval.approval_type),
                      color: '#c7d2e0',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 'bold'
                    }}>
                      {approval.approval_type.replace('_', ' ').toUpperCase()}
                    </span>
                    <span style={{ fontSize: '11px', color: '#6B7280' }}>
                      {formatDate(approval.created_at)}
                    </span>
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#E5E7EB', marginBottom: '4px' }}>
                    {approval.title}
                  </div>
                  <div style={{ fontSize: '12px', color: '#9CA3AF' }}>
                    {approval.program_name || 'Unknown Program'}
                  </div>
                  {approval.content.findings_count !== undefined && (
                    <div style={{ fontSize: '11px', color: '#D97706', marginTop: '4px' }}>
                      {approval.content.findings_count} findings
                      {approval.content.critical_count ? ` (${approval.content.critical_count} critical)` : ''}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail View */}
        <div style={{
          background: '#1A1A1A',
          border: '1px solid #2A2A2A',
          borderRadius: '8px',
          padding: '24px',
          maxHeight: '700px',
          overflowY: 'auto'
        }}>
          {!selected ? (
            <div style={{ textAlign: 'center', padding: '80px', color: '#9CA3AF' }}>
              ← Select an approval request to review
            </div>
          ) : (
            <div>
              {/* Header */}
              <div style={{ marginBottom: '24px' }}>
                <h2 style={{ fontSize: '20px', color: '#355E3B', marginBottom: '8px' }}>
                  {selected.title}
                </h2>
                <p style={{ color: '#9CA3AF', fontSize: '14px' }}>
                  {selected.description}
                </p>
              </div>

              {/* Email Draft Preview */}
              {selected.content.email_draft && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <h3 style={{ fontSize: '16px', color: '#355E3B' }}>
                      📧 Email Draft
                    </h3>
                    <button
                      onClick={copyEmailToClipboard}
                      style={{
                        background: '#2A2A2A',
                        border: '1px solid #355E3B',
                        color: '#355E3B',
                        padding: '4px 12px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      📋 Copy Email
                    </button>
                  </div>

                  <div style={{
                    background: '#0F0F0F',
                    border: '1px solid #2A2A2A',
                    borderRadius: '8px',
                    padding: '16px',
                    marginBottom: '24px'
                  }}>
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '12px', color: '#9CA3AF' }}>To:</div>
                      <div style={{ fontSize: '14px', color: '#E5E7EB' }}>
                        {selected.content.email_draft.to}
                      </div>
                    </div>
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ fontSize: '12px', color: '#9CA3AF' }}>Subject:</div>
                      <div style={{ fontSize: '14px', color: '#E5E7EB', fontWeight: 'bold' }}>
                        {selected.content.email_draft.subject}
                      </div>
                    </div>
                    <div style={{ borderTop: '1px solid #2A2A2A', paddingTop: '16px' }}>
                      <div style={{ fontSize: '12px', color: '#9CA3AF', marginBottom: '8px' }}>Body:</div>
                      <div
                        style={{
                          fontSize: '13px',
                          color: '#D1D5DB',
                          maxHeight: '300px',
                          overflowY: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                        dangerouslySetInnerHTML={{
                          __html: DOMPurify.sanitize(selected.content.email_draft.body, {
                            ALLOWED_TAGS: ['p', 'br', 'b', 'i', 'u', 'strong', 'em', 'a', 'ul', 'ol', 'li'],
                            ALLOWED_ATTR: ['href'],
                            FORBID_ATTR: ['onerror', 'onload'],
                            ALLOWED_URI_REGEXP: /^(https?|mailto):/i,
                          }),
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={handleApprove}
                  disabled={actionInProgress}
                  style={{
                    flex: 1,
                    background: '#10B981',
                    color: '#c7d2e0',
                    border: 'none',
                    padding: '12px 24px',
                    borderRadius: '8px',
                    cursor: actionInProgress ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}
                >
                  {actionInProgress ? 'Processing...' : '✅ Approve Draft'}
                </button>
                <button
                  onClick={() => setShowRejectModal(true)}
                  disabled={actionInProgress}
                  style={{
                    flex: 1,
                    background: '#EF4444',
                    color: '#c7d2e0',
                    border: 'none',
                    padding: '12px 24px',
                    borderRadius: '8px',
                    cursor: actionInProgress ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}
                >
                  {actionInProgress ? 'Processing...' : '❌ Reject Draft'}
                </button>
              </div>

              <div style={{
                marginTop: '16px',
                padding: '12px',
                background: '#FEF3C7',
                border: '1px solid #D97706',
                borderRadius: '8px',
                color: '#92400E',
                fontSize: '13px'
              }}>
                ⚠️ After approving, you must manually send this email via your email client.
                The platform NEVER auto-sends emails.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#1A1A1A',
            border: '1px solid #2A2A2A',
            borderRadius: '12px',
            padding: '24px',
            maxWidth: '500px',
            width: '90%'
          }}>
            <h3 style={{ color: '#EF4444', marginBottom: '16px' }}>
              Reject Draft
            </h3>
            <p style={{ color: '#9CA3AF', fontSize: '14px', marginBottom: '16px' }}>
              Please provide a reason for rejecting this draft:
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              style={{
                width: '100%',
                minHeight: '100px',
                background: '#0F0F0F',
                border: '1px solid #2A2A2A',
                borderRadius: '8px',
                padding: '12px',
                color: '#E5E7EB',
                fontSize: '14px',
                marginBottom: '16px',
                resize: 'vertical'
              }}
            />
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || actionInProgress}
                style={{
                  flex: 1,
                  background: '#EF4444',
                  color: '#c7d2e0',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: '8px',
                  cursor: !rejectReason.trim() || actionInProgress ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold'
                }}
              >
                Reject
              </button>
              <button
                onClick={() => {
                  setShowRejectModal(false);
                  setRejectReason('');
                }}
                style={{
                  flex: 1,
                  background: '#2A2A2A',
                  color: '#E5E7EB',
                  border: '1px solid #4B5563',
                  padding: '10px 20px',
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Stats Card Component
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: '#1A1A1A',
      border: '1px solid #2A2A2A',
      borderRadius: '8px',
      padding: '16px',
      textAlign: 'center'
    }}>
      <div style={{ fontSize: '12px', color: '#9CA3AF', marginBottom: '8px' }}>
        {label}
      </div>
      <div style={{ fontSize: '32px', fontWeight: 'bold', color }}>
        {value}
      </div>
    </div>
  );
}

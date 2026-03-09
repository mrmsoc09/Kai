/**
 * Approval dialog for HiL (Human-in-the-Loop) approval workflow
 * Integrates with existing approval_workflow.py
 */

import React, { useState } from 'react';
import { COLORS, UI } from '@/theme/branding';
import type { ApprovalRequest } from './hooks/useAgentZeroStream';

interface ApprovalDialogProps {
  approval: ApprovalRequest;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string, reason: string) => void;
  onClose: () => void;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  approval,
  onApprove,
  onReject,
  onClose,
}) => {
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  const handleApprove = () => {
    onApprove(approval.approvalId);
    onClose();
  };

  const handleReject = () => {
    if (!showRejectInput) {
      setShowRejectInput(true);
      return;
    }

    if (!rejectReason.trim()) {
      alert('Please provide a reason for rejection');
      return;
    }

    onReject(approval.approvalId, rejectReason);
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          animation: 'fadeIn 0.2s ease-in',
        }}
        onClick={onClose}
      >
        {/* Dialog */}
        <div
          style={{
            backgroundColor: COLORS.surface,
            borderRadius: UI.borderRadius.large,
            boxShadow: UI.shadow.xl,
            maxWidth: '600px',
            width: '90%',
            maxHeight: '80vh',
            overflow: 'auto',
            animation: 'slideUp 0.3s ease-out',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div
            style={{
              padding: UI.spacing.lg,
              borderBottom: `1px solid ${COLORS.neutral.gray_200}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.sm }}>
              <span style={{ fontSize: '24px' }}>⚠️</span>
              <h2 style={{ margin: 0, fontSize: UI.fonts.size_xl, fontWeight: 600 }}>
                Approval Required
              </h2>
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                fontSize: UI.fonts.size_xl,
                cursor: 'pointer',
                color: COLORS.neutral.gray_500,
                padding: UI.spacing.xs,
              }}
            >
              ✕
            </button>
          </div>

          {/* Body */}
          <div style={{ padding: UI.spacing.lg }}>
            {/* Operation Info */}
            <div
              style={{
                backgroundColor: COLORS.status.warning + '10',
                padding: UI.spacing.md,
                borderRadius: UI.borderRadius.medium,
                border: `2px solid ${COLORS.status.warning}`,
                marginBottom: UI.spacing.lg,
              }}
            >
              <div
                style={{
                  fontSize: UI.fonts.size_sm,
                  fontWeight: 600,
                  marginBottom: UI.spacing.xs,
                  color: COLORS.status.warning,
                }}
              >
                OPERATION
              </div>
              <div style={{ fontSize: UI.fonts.size_lg, fontWeight: 600, marginBottom: UI.spacing.sm }}>
                {approval.operation}
              </div>
              <div style={{ fontSize: UI.fonts.size_sm, color: COLORS.neutral.gray_600 }}>
                {approval.message}
              </div>
            </div>

            {/* Tier Badge */}
            <div style={{ marginBottom: UI.spacing.lg }}>
              <span
                style={{
                  display: 'inline-block',
                  padding: `${UI.spacing.xs} ${UI.spacing.md}`,
                  backgroundColor:
                    approval.tier >= 3
                  ? COLORS.severity.critical
                  : approval.tier >= 2
                  ? COLORS.status.warning
                  : COLORS.status.info,
                  color: COLORS.textInverse,
                  borderRadius: UI.borderRadius.medium,
                  fontSize: UI.fonts.size_sm,
                  fontWeight: 600,
                }}
              >
                🛡️ TIER {approval.tier} OPERATION
              </span>
              <div
                style={{
                  marginTop: UI.spacing.sm,
                  fontSize: UI.fonts.size_sm,
                  color: COLORS.neutral.gray_600,
                }}
              >
                {approval.tier >= 3
                  ? 'Critical operation requiring explicit approval'
                  : approval.tier >= 2
                  ? 'Elevated operation requiring approval'
                  : 'Standard operation requiring approval'}
              </div>
            </div>

            {/* Details */}
            {Object.keys(approval.details).length > 0 && (
              <div style={{ marginBottom: UI.spacing.lg }}>
                <h3
                  style={{
                    fontSize: UI.fonts.size_base,
                    fontWeight: 600,
                    marginBottom: UI.spacing.sm,
                  }}
                >
                  Operation Details
                </h3>
                <div
                  style={{
                    backgroundColor: COLORS.neutral.gray_50,
                    padding: UI.spacing.md,
                    borderRadius: UI.borderRadius.medium,
                    fontFamily: UI.fonts.family_mono,
                    fontSize: UI.fonts.size_sm,
                    overflow: 'auto',
                    maxHeight: '200px',
                  }}
                >
                  <pre style={{ margin: 0 }}>
                    {JSON.stringify(approval.details, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Reject Reason Input */}
            {showRejectInput && (
              <div style={{ marginBottom: UI.spacing.lg }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: UI.fonts.size_sm,
                    fontWeight: 600,
                    marginBottom: UI.spacing.xs,
                  }}
                >
                  Reason for Rejection
                </label>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Please provide a reason for rejecting this operation..."
                  style={{
                    width: '100%',
                    minHeight: '100px',
                    padding: UI.spacing.sm,
                    borderRadius: UI.borderRadius.medium,
                    border: `1px solid ${COLORS.neutral.gray_300}`,
                    fontSize: UI.fonts.size_base,
                    fontFamily: UI.fonts.family_sans,
                    resize: 'vertical',
                  }}
                  autoFocus
                />
              </div>
            )}

            {/* Security Notice */}
            <div
              style={{
                backgroundColor: COLORS.status.info + '10',
                padding: UI.spacing.md,
                borderRadius: UI.borderRadius.medium,
                border: `1px solid ${COLORS.status.info}`,
                marginBottom: UI.spacing.lg,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  gap: UI.spacing.sm,
                  fontSize: UI.fonts.size_sm,
                  color: COLORS.neutral.gray_700,
                }}
              >
                <span>ℹ️</span>
                <div>
                  <strong>Security Notice:</strong> This operation will be logged with a
                  cryptographic signature in the audit trail. Your approval decision is
                  permanent and cannot be modified.
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div
            style={{
              padding: UI.spacing.lg,
              borderTop: `1px solid ${COLORS.neutral.gray_200}`,
              display: 'flex',
              justifyContent: 'flex-end',
              gap: UI.spacing.md,
              backgroundColor: COLORS.neutral.gray_50,
            }}
          >
            <button
              onClick={onClose}
              style={{
                padding: `${UI.spacing.sm} ${UI.spacing.lg}`,
                borderRadius: UI.borderRadius.medium,
                border: `1px solid ${COLORS.neutral.gray_300}`,
                backgroundColor: COLORS.neutral.gray_100,
                color: COLORS.textSecondary,
                fontSize: UI.fonts.size_base,
                fontWeight: 600,
                cursor: 'pointer',
                transition: `all ${UI.transition.base}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = COLORS.neutral.gray_100;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = COLORS.neutral.gray_100;
              }}
            >
              Cancel
            </button>

            <button
              onClick={handleReject}
              style={{
                padding: `${UI.spacing.sm} ${UI.spacing.lg}`,
                borderRadius: UI.borderRadius.medium,
                border: 'none',
                backgroundColor: COLORS.status.error,
                color: COLORS.textInverse,
                fontSize: UI.fonts.size_base,
                fontWeight: 600,
                cursor: 'pointer',
                transition: `all ${UI.transition.base}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = '0.9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '1';
              }}
            >
              {showRejectInput ? 'Confirm Rejection' : 'Reject'}
            </button>

            <button
              onClick={handleApprove}
              style={{
                padding: `${UI.spacing.sm} ${UI.spacing.lg}`,
                borderRadius: UI.borderRadius.medium,
                border: 'none',
                backgroundColor: COLORS.status.success,
                color: COLORS.textInverse,
                fontSize: UI.fonts.size_base,
                fontWeight: 600,
                cursor: 'pointer',
                transition: `all ${UI.transition.base}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#16a34a';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = COLORS.status.success;
              }}
            >
              ✓ Approve Operation
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes slideUp {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
      `}</style>
    </>
  );
};

export default ApprovalDialog;

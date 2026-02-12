/**
 * HiL Approval API Client
 * Manages Human-in-the-Loop approval workflow for reports and emails
 */

const BASE_URL = '/api/v1/approval';

export interface ApprovalRequest {
  approval_id: string;
  approval_type: string;
  status: string;
  created_at: string;
  title: string;
  description: string;
  content: {
    email_draft?: {
      to: string;
      subject: string;
      body: string;
    };
    report?: any;
    findings_count?: number;
    critical_count?: number;
  };
  scan_id?: string;
  program_id?: string;
  program_name?: string;
  approved_by?: string;
  approved_at?: string;
  rejection_reason?: string;
  user_notes?: string;
}

export interface ApprovalListResponse {
  approvals: ApprovalRequest[];
  total_pending: number;
  total_approved: number;
  total_rejected: number;
}

export interface ApprovalStats {
  total_requests: number;
  pending: number;
  approved: number;
  rejected: number;
  cancelled: number;
  by_type: {
    report_submission: number;
    email_reply: number;
  };
  oldest_pending?: {
    approval_id: string;
    created_at: string;
    title: string;
  };
  newest_pending?: {
    approval_id: string;
    created_at: string;
    title: string;
  };
}

/**
 * List pending approval requests
 */
export async function listPendingApprovals(token: string): Promise<ApprovalListResponse> {
  const resp = await fetch(`${BASE_URL}/pending`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) throw new Error(`Failed to fetch pending approvals: ${resp.statusText}`);
  return resp.json();
}

/**
 * List all approval requests with filters
 */
export async function listAllApprovals(
  token: string,
  filters?: {
    status?: string;
    approval_type?: string;
    limit?: number;
  }
): Promise<ApprovalListResponse> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status_filter', filters.status);
  if (filters?.approval_type) params.set('approval_type', filters.approval_type);
  if (filters?.limit) params.set('limit', String(filters.limit));

  const url = `${BASE_URL}/all?${params}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) throw new Error(`Failed to fetch approvals: ${resp.statusText}`);
  return resp.json();
}

/**
 * Get specific approval request
 */
export async function getApproval(approvalId: string, token: string): Promise<ApprovalRequest> {
  const resp = await fetch(`${BASE_URL}/${approvalId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) throw new Error(`Failed to fetch approval: ${resp.statusText}`);
  return resp.json();
}

/**
 * Approve an approval request
 */
export async function approveRequest(
  approvalId: string,
  userId: string,
  notes: string | undefined,
  token: string
): Promise<ApprovalRequest> {
  const resp = await fetch(`${BASE_URL}/${approvalId}/approve`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ user_id: userId, notes })
  });
  if (!resp.ok) throw new Error(`Failed to approve request: ${resp.statusText}`);
  return resp.json();
}

/**
 * Reject an approval request
 */
export async function rejectRequest(
  approvalId: string,
  userId: string,
  reason: string,
  token: string
): Promise<ApprovalRequest> {
  const resp = await fetch(`${BASE_URL}/${approvalId}/reject`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ user_id: userId, reason })
  });
  if (!resp.ok) throw new Error(`Failed to reject request: ${resp.statusText}`);
  return resp.json();
}

/**
 * Update draft content
 */
export async function updateDraft(
  approvalId: string,
  content: any,
  notes: string | undefined,
  token: string
): Promise<ApprovalRequest> {
  const resp = await fetch(`${BASE_URL}/${approvalId}/update`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ content, notes })
  });
  if (!resp.ok) throw new Error(`Failed to update draft: ${resp.statusText}`);
  return resp.json();
}

/**
 * Cancel approval request
 */
export async function cancelApproval(approvalId: string, token: string): Promise<void> {
  const resp = await fetch(`${BASE_URL}/${approvalId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) throw new Error(`Failed to cancel approval: ${resp.statusText}`);
}

/**
 * Get approval statistics
 */
export async function getApprovalStats(token: string): Promise<ApprovalStats> {
  const resp = await fetch(`${BASE_URL}/stats/summary`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) throw new Error(`Failed to fetch stats: ${resp.statusText}`);
  return resp.json();
}

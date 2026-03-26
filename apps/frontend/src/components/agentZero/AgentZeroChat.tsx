/**
 * Kaison Composer Chat Interface
 * Main chat component with streaming, tool calls, and HiL approval integration.
 *
 * Orchestration is handled by Gemini CLI. See orchestration/gemini_orchestrator.py.
 */

import React, { useState, useRef, useEffect } from 'react';
import { COLORS, UI } from '@/theme/branding';
import { useOrchestrationStream } from './hooks/useOrchestrationStream';
import { ChatMessage } from './ChatMessage';
import { ApprovalDialog } from './ApprovalDialog';
import type { ApprovalRequest } from './hooks/useOrchestrationStream';

export const OrchestrationChat: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [currentApproval, setCurrentApproval] = useState<ApprovalRequest | null>(null);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [ragContext, setRagContext] = useState<string>('');
  const [fetchingContext, setFetchingContext] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    isConnected,
    isStreaming,
    sessionId,
    messages,
    pendingApprovals,
    streamingContent,
    sendMessage,
    approveRequest,
    rejectRequest,
    clearHistory,
  } = useOrchestrationStream({
    onApprovalRequired: (approval) => {
      setCurrentApproval(approval);
    },
    onError: (error) => {
      console.error('Chat error:', error);
    },
  });

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const fetchRAGContext = async (query: string): Promise<string> => {
    try {
      setFetchingContext(true);
      const res = await fetch('/api/v1/intelligence/rag/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 3 }),
      });

      const data = await res.json();

      if (data.success && data.data.answer) {
        return data.data.answer;
      }
      return '';
    } catch (error) {
      console.error('Failed to fetch RAG context:', error);
      return '';
    } finally {
      setFetchingContext(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !isConnected) return;

    const userMessage = inputValue.trim();
    setInputValue('');

    // Fetch RAG context if enabled
    let context = '';
    if (ragEnabled) {
      context = await fetchRAGContext(userMessage);
      setRagContext(context);
    }

    // Send message with optional RAG context
    const enhancedMessage = ragEnabled && context
      ? `[RAG Context: ${context}]\n\nUser Query: ${userMessage}`
      : userMessage;

    sendMessage(enhancedMessage);
  };

  const handleApprove = (approvalId: string) => {
    approveRequest(approvalId);
  };

  const handleReject = (approvalId: string, reason: string) => {
    rejectRequest(approvalId, reason);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: COLORS.background,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: UI.spacing.lg,
          backgroundColor: COLORS.surface,
          borderBottom: `1px solid ${COLORS.neutral.gray_200}`,
          boxShadow: UI.shadow.sm,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.md }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: COLORS.primary.main,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '20px',
              }}
            >
              🤖
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: UI.fonts.size_xl, fontWeight: 600 }}>
                Kaison Composer
              </h2>
              <p
                style={{
                  margin: 0,
                  fontSize: UI.fonts.size_sm,
                  color: COLORS.neutral.gray_600,
                }}
              >
                AI Security Operations Assistant
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.md }}>
            {/* Connection Status */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: UI.spacing.xs,
                fontSize: UI.fonts.size_sm,
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: isConnected ? COLORS.status.success : COLORS.status.error,
                }}
              />
              <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
            </div>

            {/* RAG Toggle */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: UI.spacing.xs,
                fontSize: UI.fonts.size_sm,
              }}
            >
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={ragEnabled}
                  onChange={(e) => setRagEnabled(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ color: ragEnabled ? COLORS.primary.main : COLORS.neutral.gray_600 }}>
                  🧠 RAG {fetchingContext && '(fetching...)'}
                </span>
              </label>
            </div>

            {/* Clear Button */}
            <button
              onClick={clearHistory}
              style={{
                padding: `${UI.spacing.xs} ${UI.spacing.sm}`,
                borderRadius: UI.borderRadius.medium,
                border: `1px solid ${COLORS.neutral.gray_300}`,
                backgroundColor: COLORS.neutral.gray_100,
                color: COLORS.textSecondary,
                fontSize: UI.fonts.size_sm,
                cursor: 'pointer',
              }}
            >
              Clear History
            </button>
          </div>
        </div>

        {/* Pending Approvals Banner */}
        {pendingApprovals.length > 0 && (
          <div
            style={{
              marginTop: UI.spacing.md,
              padding: UI.spacing.md,
              backgroundColor: COLORS.status.warning + '15',
              borderRadius: UI.borderRadius.medium,
              border: `1px solid ${COLORS.status.warning}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.sm }}>
              <span style={{ fontSize: '20px' }}>⚠️</span>
              <span style={{ fontSize: UI.fonts.size_sm, fontWeight: 600 }}>
                {pendingApprovals.length} operation(s) awaiting approval
              </span>
            </div>
            <button
              onClick={() => setCurrentApproval(pendingApprovals[0])}
              style={{
                padding: `${UI.spacing.xs} ${UI.spacing.md}`,
                borderRadius: UI.borderRadius.medium,
                border: 'none',
                backgroundColor: COLORS.status.warning,
                color: COLORS.textInverse,
                fontSize: UI.fonts.size_sm,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Review
            </button>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: UI.spacing.lg,
        }}
      >
        {/* Welcome Message */}
        {messages.length === 0 && !streamingContent && (
          <div
            style={{
              textAlign: 'center',
              padding: UI.spacing.xxl,
              color: COLORS.neutral.gray_500,
            }}
          >
            <div style={{ fontSize: '48px', marginBottom: UI.spacing.md }}>🤖</div>
            <h3 style={{ fontSize: UI.fonts.size_lg, marginBottom: UI.spacing.sm }}>
              Welcome to Kaison Composer
            </h3>
            <p style={{ fontSize: UI.fonts.size_base, marginBottom: UI.spacing.lg }}>
              I can help you with security operations, vulnerability hunting, and more.
            </p>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: UI.spacing.sm,
                alignItems: 'center',
              }}
            >
              <p style={{ fontSize: UI.fonts.size_sm, fontWeight: 600 }}>Try asking:</p>
              {[
                'Hunt for vulnerabilities in example.com',
                'Run a nuclei scan on target.com',
                'Show me the current findings',
                'What agents are currently active?',
              ].map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => setInputValue(example)}
                  style={{
                    padding: `${UI.spacing.sm} ${UI.spacing.md}`,
                    borderRadius: UI.borderRadius.medium,
                    border: `1px solid ${COLORS.neutral.gray_300}`,
                    backgroundColor: COLORS.neutral.gray_100,
                    color: COLORS.textSecondary,
                    fontSize: UI.fonts.size_sm,
                    cursor: 'pointer',
                    maxWidth: '400px',
                    textAlign: 'left',
                  }}
                >
                  "{example}"
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Streaming Message */}
        {isStreaming && streamingContent && (
          <ChatMessage
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              timestamp: new Date().toISOString(),
            }}
            isStreaming={true}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div
        style={{
          padding: UI.spacing.lg,
          backgroundColor: COLORS.surface,
          borderTop: `1px solid ${COLORS.neutral.gray_200}`,
          boxShadow: '0 -2px 10px rgba(0,0,0,0.05)',
        }}
      >
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: UI.spacing.md }}>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={
              isConnected
                ? 'Ask Kaison Composer anything...'
                : 'Connecting to Kaison Composer...'
            }
            disabled={!isConnected || isStreaming}
            style={{
              flex: 1,
              padding: UI.spacing.md,
              borderRadius: UI.borderRadius.medium,
              border: `1px solid ${COLORS.neutral.gray_300}`,
              fontSize: UI.fonts.size_base,
              outline: 'none',
              transition: `border ${UI.transition.base}`,
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = COLORS.primary.main;
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = COLORS.neutral.gray_300;
            }}
          />

          <button
            type="submit"
            disabled={!isConnected || !inputValue.trim() || isStreaming}
            style={{
              padding: `${UI.spacing.md} ${UI.spacing.xl}`,
              borderRadius: UI.borderRadius.medium,
              border: 'none',
              backgroundColor: isConnected && inputValue.trim() && !isStreaming
                ? COLORS.primary.main
                : COLORS.neutral.gray_300,
              color: COLORS.textInverse,
              fontSize: UI.fonts.size_base,
              fontWeight: 600,
              cursor: isConnected && inputValue.trim() && !isStreaming ? 'pointer' : 'not-allowed',
              transition: `all ${UI.transition.base}`,
            }}
          >
            {isStreaming ? '...' : 'Send'}
          </button>
        </form>

        <div
          style={{
            marginTop: UI.spacing.sm,
            fontSize: UI.fonts.size_xs,
            color: COLORS.neutral.gray_500,
            textAlign: 'center',
          }}
        >
          {sessionId && `Session: ${sessionId.substring(0, 8)}`}
          {' • '}
          Kaison Composer integrates with K1's security orchestration and HiL approval workflow
        </div>
      </div>

      {/* Approval Dialog */}
      {currentApproval && (
        <ApprovalDialog
          approval={currentApproval}
          onApprove={handleApprove}
          onReject={handleReject}
          onClose={() => setCurrentApproval(null)}
        />
      )}
    </div>
  );
};

export default OrchestrationChat;

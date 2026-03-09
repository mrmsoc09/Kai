/**
 * Chat message component with support for tool calls and streaming
 */

import React from 'react';
import { COLORS, UI } from '@/theme/branding';
import type { ChatMessage as ChatMessageType, ToolCall } from './hooks/useAgentZeroStream';

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isStreaming }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isTool = message.role === 'tool';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: UI.spacing.md,
        animation: 'fadeIn 0.3s ease-in',
      }}
    >
      <div
        style={{
          maxWidth: '70%',
          padding: UI.spacing.md,
          borderRadius: UI.borderRadius.large,
          backgroundColor: isUser
            ? COLORS.primary.main
            : isSystem
            ? COLORS.neutral.gray_100
            : isTool
            ? COLORS.status.info + '15'
            : COLORS.surface,
          color: isUser ? COLORS.textInverse : COLORS.text,
          border: isUser ? 'none' : `1px solid ${COLORS.neutral.gray_200}`,
          boxShadow: UI.shadow.sm,
        }}
      >
        {/* Message Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: UI.spacing.xs,
            fontSize: UI.fonts.size_xs,
            opacity: 0.7,
            gap: UI.spacing.xs,
          }}
        >
          <span style={{ fontWeight: 600 }}>
            {message.role === 'user'
              ? 'You'
              : message.role === 'assistant'
              ? 'Kaison Composer'
              : message.role === 'tool'
              ? `Tool: ${message.metadata?.tool || 'Unknown'}`
              : 'System'}
          </span>
          <span>•</span>
          <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
        </div>

        {/* Message Content */}
        <div
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: isTool ? UI.fonts.family_mono : UI.fonts.family_sans,
            fontSize: isTool ? UI.fonts.size_sm : UI.fonts.size_base,
            lineHeight: 1.5,
          }}
        >
          {message.content}
          {isStreaming && (
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '16px',
                backgroundColor: COLORS.primary.main,
                marginLeft: '2px',
                animation: 'blink 1s infinite',
              }}
            />
          )}
        </div>

        {/* Tool Calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div style={{ marginTop: UI.spacing.md }}>
            {message.toolCalls.map((toolCall, idx) => (
              <ToolCallDisplay key={idx} toolCall={toolCall} />
            ))}
          </div>
        )}

        {/* Approval Badge */}
        {message.approvalRequired && (
          <div
            style={{
              marginTop: UI.spacing.sm,
              padding: `${UI.spacing.xs} ${UI.spacing.sm}`,
              backgroundColor: COLORS.status.warning + '20',
              borderRadius: UI.borderRadius.small,
              fontSize: UI.fonts.size_xs,
              color: COLORS.status.warning,
              fontWeight: 600,
            }}
          >
            ⚠ Approval Required
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes blink {
          0%, 50% {
            opacity: 1;
          }
          51%, 100% {
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
};

/**
 * Tool call display component
 */
const ToolCallDisplay: React.FC<{ toolCall: ToolCall }> = ({ toolCall }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <div
      style={{
        padding: UI.spacing.sm,
        backgroundColor: COLORS.neutral.gray_50,
        borderRadius: UI.borderRadius.small,
        border: `1px solid ${COLORS.neutral.gray_200}`,
        marginTop: UI.spacing.xs,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.xs }}>
          <span style={{ fontSize: UI.fonts.size_sm }}>🔧</span>
          <span style={{ fontSize: UI.fonts.size_sm, fontWeight: 600 }}>
            {toolCall.tool}
          </span>
          {toolCall.tier !== undefined && (
            <span
              style={{
                fontSize: UI.fonts.size_xs,
                padding: '2px 6px',
                backgroundColor:
                  toolCall.tier >= 2 ? COLORS.status.warning : COLORS.status.info,
                color: COLORS.textInverse,
                borderRadius: UI.borderRadius.small,
                fontWeight: 600,
              }}
            >
              TIER {toolCall.tier}
            </span>
          )}
        </div>
        <span style={{ fontSize: UI.fonts.size_xs, opacity: 0.7 }}>
          {isExpanded ? '▼' : '▶'}
        </span>
      </div>

      {toolCall.description && (
        <div
          style={{
            fontSize: UI.fonts.size_xs,
            marginTop: UI.spacing.xs,
            opacity: 0.8,
          }}
        >
          {toolCall.description}
        </div>
      )}

      {isExpanded && Object.keys(toolCall.params).length > 0 && (
        <div
          style={{
            marginTop: UI.spacing.sm,
            padding: UI.spacing.sm,
            backgroundColor: COLORS.elevated,
            borderRadius: UI.borderRadius.small,
            fontFamily: UI.fonts.family_mono,
            fontSize: UI.fonts.size_xs,
            overflow: 'auto',
          }}
        >
          <pre style={{ margin: 0 }}>{JSON.stringify(toolCall.params, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default ChatMessage;

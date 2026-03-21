import { useEffect, useRef, useState } from 'react';

interface ActionModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  requiresReason?: boolean;
  reasonPlaceholder?: string;
  confirmLabel: string;
  confirmClass?: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

/**
 * Inline modal that replaces window.prompt / window.confirm throughout the UI.
 * Renders a focused overlay with an optional reason textarea.
 */
export function ActionModal({
  isOpen,
  title,
  message,
  requiresReason = false,
  reasonPlaceholder = 'Optional reason...',
  confirmLabel,
  confirmClass = 'bg-cyan-500/20 text-cyan-200 hover:bg-cyan-500/30',
  onConfirm,
  onCancel,
}: ActionModalProps) {
  const [reason, setReason] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isOpen) {
      setReason('');
      if (requiresReason) {
        window.setTimeout(() => textareaRef.current?.focus(), 50);
      }
    }
  }, [isOpen, requiresReason]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
      if (event.key === 'Enter' && !requiresReason && !event.shiftKey) onConfirm(reason);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onCancel, onConfirm, reason, requiresReason]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="action-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <section className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <h2 id="action-modal-title" className="text-sm font-semibold text-slate-100">{title}</h2>
        <p className="mt-2 text-sm text-slate-300">{message}</p>

        {requiresReason ? (
          <textarea
            ref={textareaRef}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={reasonPlaceholder}
            rows={3}
            className="mt-4 w-full resize-none rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-700 px-4 py-2 text-xs text-slate-200 hover:border-slate-500"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(reason)}
            className={`rounded border border-transparent px-4 py-2 text-xs font-medium ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'danger' | 'default';
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  icon?: ReactNode;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'default',
  busy = false,
  onConfirm,
  onCancel,
  icon,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel();
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [busy, onCancel, open]);

  if (!open) return null;

  const confirmButtonClass =
    tone === 'danger'
      ? 'px-4 py-2.5 rounded-lg font-medium text-sm bg-red-500/90 text-white hover:bg-red-500 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed'
      : 'btn-primary';

  return createPortal(
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close confirmation dialog"
        style={{ position: 'absolute', inset: 0 }}
        className="bg-[#050510]/70 backdrop-blur-sm"
        onClick={busy ? undefined : onCancel}
      />

      {/* Dialog panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        style={{ position: 'relative', zIndex: 10000, width: '100%', maxWidth: '32rem' }}
        className="card page-transition border-red-500/20 p-6 shadow-[0_24px_64px_rgba(0,0,0,0.45)]"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div className="min-w-0 flex items-start gap-3">
            <div className="mt-0.5 rounded-xl border border-red-500/20 bg-red-500/10 p-2 text-red-300">
              {icon ?? <AlertTriangle className="h-5 w-5" />}
            </div>
            <div className="min-w-0 flex-1">
              <h3 id="confirm-dialog-title" className="break-words text-lg font-semibold text-white">
                {title}
              </h3>
              <p className="mt-2 break-words whitespace-pre-wrap text-sm leading-6 text-gray-400">
                {description}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={onCancel} disabled={busy} className="btn-secondary">
            {cancelLabel}
          </button>
          <button type="button" onClick={onConfirm} disabled={busy} className={confirmButtonClass}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

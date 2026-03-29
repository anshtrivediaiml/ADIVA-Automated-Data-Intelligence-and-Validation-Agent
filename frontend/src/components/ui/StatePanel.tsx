import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatePanelProps {
  title: string;
  message: string;
  icon?: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  actionTo?: string;
  tone?: 'default' | 'error' | 'success';
  compact?: boolean;
  loading?: boolean;
  className?: string;
}

export function StatePanel({
  title,
  message,
  icon,
  actionLabel,
  onAction,
  actionTo,
  tone = 'default',
  compact = false,
  loading = false,
  className,
}: StatePanelProps) {
  const toneClasses: Record<string, string> = {
    default: 'border-[#2A2A3E] bg-[#0F0F1A]',
    error: 'border-red-500/25 bg-[linear-gradient(180deg,rgba(58,19,24,0.45),rgba(15,15,26,0.96))]',
    success: 'border-green-500/20 bg-[linear-gradient(180deg,rgba(20,54,40,0.32),rgba(15,15,26,0.96))]',
  };

  const action = actionLabel && actionTo ? (
    <Link to={actionTo} className="btn-primary text-sm">
      {actionLabel}
    </Link>
  ) : actionLabel && onAction ? (
    <button type="button" onClick={onAction} className="btn-secondary text-sm">
      {actionLabel}
    </button>
  ) : null;

  return (
    <div
      className={cn(
        'rounded-2xl border px-6 text-center',
        compact ? 'py-8' : 'py-12',
        toneClasses[tone],
        className,
      )}
    >
      <div className="mx-auto flex max-w-xl flex-col items-center gap-3 text-gray-400">
        <div className="rounded-2xl border border-white/5 bg-white/[0.03] p-3 text-gray-500">
          {loading ? <Loader2 className="h-8 w-8 animate-spin text-[#A5B4FC]" /> : icon ?? <AlertTriangle className="h-8 w-8" />}
        </div>
        <div>
          <h3 className="text-sm font-medium text-white">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-gray-400">{message}</p>
        </div>
        {action ? <div className="pt-1">{action}</div> : null}
      </div>
    </div>
  );
}

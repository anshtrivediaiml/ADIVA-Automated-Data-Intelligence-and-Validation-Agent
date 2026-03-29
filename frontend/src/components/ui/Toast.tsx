import { CheckCircle2, Info, AlertTriangle, XCircle, X } from 'lucide-react';
import type { ToastItem, ToastKind } from '@/components/ui/ToastProvider';

const CONFIGS: Record<ToastKind, { icon: React.ReactNode; border: string; text: string; bg: string }> = {
  success: {
    icon: <CheckCircle2 className="w-4 h-4 flex-shrink-0" />,
    border: 'border-green-500/40',
    text: 'text-green-300',
    bg: 'bg-green-900/30',
  },
  error: {
    icon: <XCircle className="w-4 h-4 flex-shrink-0" />,
    border: 'border-red-500/40',
    text: 'text-red-300',
    bg: 'bg-red-900/30',
  },
  warning: {
    icon: <AlertTriangle className="w-4 h-4 flex-shrink-0" />,
    border: 'border-amber-500/40',
    text: 'text-amber-300',
    bg: 'bg-amber-900/30',
  },
  info: {
    icon: <Info className="w-4 h-4 flex-shrink-0" />,
    border: 'border-[#4F46E5]/40',
    text: 'text-[#A5B4FC]',
    bg: 'bg-[#4F46E5]/10',
  },
};

export function Toast({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const { icon, border, text, bg } = CONFIGS[item.kind];

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded-xl border ${border} ${bg} px-4 py-3 shadow-lg backdrop-blur-sm min-w-[280px] max-w-sm animate-[fadeSlideIn_0.2s_ease-out]`}
    >
      <span className={text}>{icon}</span>
      <p className={`flex-1 text-sm leading-snug ${text}`}>{item.message}</p>
      <button
        onClick={() => onDismiss(item.id)}
        className="text-gray-500 hover:text-white transition-colors ml-1"
        aria-label="Dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

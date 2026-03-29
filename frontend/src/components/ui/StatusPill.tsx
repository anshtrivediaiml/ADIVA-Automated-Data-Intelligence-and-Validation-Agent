import type { JobStatus } from '@/types/models';

interface StatusPillProps {
  status: JobStatus;
  className?: string;
}

const statusConfig: Record<
  JobStatus,
  { label: string; color: string; bg: string; dot: string; pulse: 'fast' | 'slow' | 'none'; title: string }
> = {
  queued: {
    label: 'Queued',
    color: 'text-gray-300',
    bg: 'bg-gray-700/50',
    dot: 'bg-gray-400',
    pulse: 'slow',
    title: 'Job is waiting in queue to be picked up by a worker',
  },
  processing: {
    label: 'Processing',
    color: 'text-blue-300',
    bg: 'bg-blue-900/30',
    dot: 'bg-blue-400',
    pulse: 'fast',
    title: 'Job is actively running through the extraction pipeline',
  },
  completed: {
    label: 'Completed',
    color: 'text-green-300',
    bg: 'bg-green-900/30',
    dot: 'bg-green-400',
    pulse: 'none',
    title: 'Extraction finished successfully — result is ready',
  },
  needs_review: {
    label: 'Needs Review',
    color: 'text-amber-300',
    bg: 'bg-amber-900/30',
    dot: 'bg-amber-400',
    pulse: 'none',
    title: 'Human review required before the result can be trusted',
  },
  low_confidence: {
    label: 'Low Confidence',
    color: 'text-orange-300',
    bg: 'bg-orange-900/30',
    dot: 'bg-orange-400',
    pulse: 'none',
    title: 'Extraction completed but confidence score is weak — verify before using',
  },
  failed: {
    label: 'Failed',
    color: 'text-red-300',
    bg: 'bg-red-900/30',
    dot: 'bg-red-400',
    pulse: 'none',
    title: 'Pipeline stopped before completion — check the job detail for the failure stage',
  },
};

const pulseClass: Record<'fast' | 'slow' | 'none', string> = {
  fast: 'animate-pulse',
  slow: 'animate-[pulse_2.8s_ease-in-out_infinite]',
  none: '',
};

export function StatusPill({ status, className = '' }: StatusPillProps) {
  const config = statusConfig[status] ?? statusConfig.failed;
  return (
    <span
      title={config.title}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color} ${className}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${config.dot} ${pulseClass[config.pulse]}`}
        aria-hidden="true"
      />
      {config.label}
    </span>
  );
}

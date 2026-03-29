import { cn } from '@/lib/utils';

interface DataPreviewProps {
  value: unknown;
  depth?: number;
  compact?: boolean;
  emptyLabel?: string;
}

export function DataPreview({
  value,
  depth = 0,
  compact = false,
  emptyLabel = 'No value',
}: DataPreviewProps) {
  if (value == null || value === '') {
    return <span className="text-sm italic text-slate-500">{emptyLabel}</span>;
  }

  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return <span className="whitespace-pre-wrap break-words text-sm text-white">{String(value)}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-sm italic text-slate-500">{emptyLabel}</span>;
    }

    const primitiveArray = value.every(
      (item) => item == null || ['string', 'number', 'boolean'].includes(typeof item),
    );

    if (primitiveArray) {
      return (
        <div className="flex flex-wrap gap-2">
          {value.map((item, index) => (
            <span
              key={index}
              className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-200"
            >
              {item == null ? 'null' : String(item)}
            </span>
          ))}
        </div>
      );
    }

    return (
      <div className={cn('space-y-3', compact && 'space-y-2')}>
        {value.map((item, index) => (
          <div
            key={index}
            className={cn(
              'rounded-2xl border border-white/10 bg-white/[0.03] p-4',
              compact && 'rounded-xl p-3',
            )}
          >
            <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">
              Item {index + 1}
            </div>
            <DataPreview value={item} depth={depth + 1} compact={compact} emptyLabel={emptyLabel} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);

    if (entries.length === 0) {
      return <span className="text-sm italic text-slate-500">{emptyLabel}</span>;
    }

    return (
      <div className="space-y-2">
        {entries.map(([key, nestedValue]) => (
          <div
            key={key}
            className={cn(
              'grid items-start gap-3 border-b border-white/6 pb-2 last:border-b-0 last:pb-0',
              depth > 1 || compact ? 'grid-cols-1' : 'grid-cols-[180px_minmax(0,1fr)]',
            )}
          >
            <div className="text-sm capitalize text-slate-400">{humanizeKey(key)}</div>
            <div className="min-w-0">
              <DataPreview value={nestedValue} depth={depth + 1} compact={compact} emptyLabel={emptyLabel} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <span className="break-words text-sm text-white">{String(value)}</span>;
}

function humanizeKey(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/\./g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

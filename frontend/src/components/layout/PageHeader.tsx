import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  badges?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  badges,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('page-header-shell', className)}>
      <div className="min-w-0 flex-1">
        {eyebrow ? (
          <div className="page-eyebrow">
            {eyebrow}
          </div>
        ) : null}
        <h1 className="page-title">{title}</h1>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
        {badges ? <div className="mt-4 flex flex-wrap items-center gap-2">{badges}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-3">{actions}</div> : null}
    </div>
  );
}

import type { ReactNode } from 'react';

export type UploadStateCardTone = 'brand' | 'green' | 'amber' | 'slate';

const TONE_CLASSES: Record<UploadStateCardTone, string> = {
  brand: 'text-[#A5B4FC]',
  green: 'text-green-300',
  amber: 'text-amber-300',
  slate: 'text-gray-300',
};

export function UploadStateCard({
  icon,
  title,
  value,
  hint,
  tone,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  hint: string;
  tone: UploadStateCardTone;
}) {
  return (
    <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] p-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 mb-2">
        <span className={TONE_CLASSES[tone]}>{icon}</span>
        {title}
      </div>
      <div className={`text-lg font-semibold mb-1 ${TONE_CLASSES[tone]}`}>{value}</div>
      <div className="text-xs text-gray-500 leading-relaxed">{hint}</div>
    </div>
  );
}

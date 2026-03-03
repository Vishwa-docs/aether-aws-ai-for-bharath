import type { Severity } from '../types';

interface StatusBadgeProps {
  severity: Severity;
  size?: 'sm' | 'md';
}

const SEVERITY_STYLES: Record<Severity, string> = {
  CRITICAL: 'bg-red-100 text-red-800 ring-red-600/20',
  HIGH: 'bg-orange-100 text-orange-800 ring-orange-600/20',
  MEDIUM: 'bg-yellow-100 text-yellow-800 ring-yellow-600/20',
  LOW: 'bg-green-100 text-green-800 ring-green-600/20',
  INFO: 'bg-gray-100 text-gray-800 ring-gray-600/20',
};

const SIZE_STYLES: Record<NonNullable<StatusBadgeProps['size']>, string> = {
  sm: 'px-2 py-0.5 text-[11px]',
  md: 'px-2.5 py-1 text-xs',
};

export default function StatusBadge({ severity, size = 'md' }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ring-1 ring-inset ${SEVERITY_STYLES[severity]} ${SIZE_STYLES[size]}`}
    >
      {severity}
    </span>
  );
}

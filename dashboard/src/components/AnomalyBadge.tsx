import { cn } from '../lib/utils';

interface AnomalyBadgeProps {
  severity: string;
  size?: 'sm' | 'md';
}

export function AnomalyBadge({ severity, size = 'sm' }: AnomalyBadgeProps) {
  const upper = severity.toUpperCase();
  const classes = cn(
    'inline-flex items-center gap-1 rounded-full font-semibold tracking-wide uppercase',
    size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
    upper === 'HIGH' && 'badge-severity-high',
    upper === 'MEDIUM' && 'badge-severity-medium',
    upper === 'LOW' && 'badge-severity-low',
  );

  const dotColor = upper === 'HIGH' ? 'bg-red-400' : upper === 'MEDIUM' ? 'bg-amber-400' : 'bg-blue-400';

  return (
    <span className={classes}>
      <span className={cn('w-1.5 h-1.5 rounded-full', dotColor)} />
      {upper}
    </span>
  );
}

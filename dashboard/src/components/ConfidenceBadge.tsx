import { cn, getConfidenceLevel } from '../lib/utils';

interface ConfidenceBadgeProps {
  confidence: number;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export function ConfidenceBadge({ confidence, showLabel = true, size = 'sm' }: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(confidence);
  const pct = (confidence * 100).toFixed(0);

  const classes = cn(
    'inline-flex items-center gap-1 rounded-full font-medium',
    size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
    level === 'high' && 'badge-confidence-high',
    level === 'medium' && 'badge-confidence-medium',
    level === 'low' && 'badge-confidence-low',
  );

  const dotColor = level === 'high' ? 'bg-green-400' : level === 'medium' ? 'bg-amber-400' : 'bg-red-400';

  return (
    <span className={classes}>
      <span className={cn('w-1.5 h-1.5 rounded-full', dotColor)} />
      {showLabel ? `${pct}%` : null}
    </span>
  );
}

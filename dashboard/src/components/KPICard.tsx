import { type ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { cn } from '../lib/utils';
import { ConfidenceBadge } from './ConfidenceBadge';

interface KPICardProps {
  title: string;
  metric: string | number;
  subtitle?: string;
  trend?: number; // positive = up, negative = down
  trendLabel?: string;
  confidence?: number;
  sparklineData?: number[];
  icon?: ReactNode;
  accentColor?: 'indigo' | 'green' | 'amber' | 'red';
  className?: string;
}

const gradients: Record<string, string> = {
  indigo: 'gradient-indigo',
  green: 'gradient-green',
  amber: 'gradient-amber',
  red: 'gradient-red',
};

const strokeColors: Record<string, string> = {
  indigo: '#7b2cb1', // Royal Purple
  green: '#ec4899', // Brand Pink/Magenta Accent
  amber: '#d4af37', // Soft Gold Accent
  red: '#ef4444',
};

export function KPICard({
  title,
  metric,
  subtitle,
  trend,
  trendLabel,
  confidence,
  sparklineData,
  icon,
  accentColor = 'indigo',
  className,
}: KPICardProps) {
  const chartData = sparklineData?.map((v, i) => ({ i, v })) ?? [];
  const hasTrend = trend !== undefined;
  const isUp = (trend ?? 0) > 0;
  const isFlat = trend === 0;

  return (
    <div className={cn('metric-card animate-slide-up', gradients[accentColor], className)}>
      {/* Top row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon && (
            <div className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center',
              accentColor === 'indigo' && 'bg-indigo-500/20 text-indigo-400',
              accentColor === 'green' && 'bg-green-500/20 text-green-400',
              accentColor === 'amber' && 'bg-amber-500/20 text-amber-400',
              accentColor === 'red' && 'bg-red-500/20 text-red-400',
            )}>
              {icon}
            </div>
          )}
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</span>
        </div>
        {confidence !== undefined && <ConfidenceBadge confidence={confidence} />}
      </div>

      {/* Metric */}
      <div className="mb-3">
        <div className="text-3xl font-bold text-white tracking-tight">{metric}</div>
        {subtitle && <div className="text-sm text-gray-400 mt-1">{subtitle}</div>}
      </div>

      {/* Trend + Sparkline */}
      <div className="flex items-end justify-between mt-2">
        {hasTrend && (
          <div className={cn(
            'flex items-center gap-1 text-xs font-medium',
            isFlat ? 'text-gray-400' : isUp ? 'text-green-400' : 'text-red-400'
          )}>
            {isFlat ? <Minus size={12} /> : isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            <span>{isUp ? '+' : ''}{trend?.toFixed(1)}%</span>
            {trendLabel && <span className="text-gray-500 ml-1">{trendLabel}</span>}
          </div>
        )}
        {chartData.length > 0 && (
          <div className="w-24 h-10 ml-auto">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={strokeColors[accentColor]}
                  strokeWidth={1.5}
                  dot={false}
                  strokeOpacity={0.8}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

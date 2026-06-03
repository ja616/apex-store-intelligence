import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../lib/utils';

interface MetricWithReasonProps {
  label: string;
  value: string | number;
  reasoning?: Record<string, string | number>;
  icon?: ReactNode;
  className?: string;
}

export function MetricWithReason({ label, value, reasoning, icon, className }: MetricWithReasonProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={cn('rounded-lg border border-[#1f2937] bg-white/2 overflow-hidden', className)}>
      <button
        onClick={() => reasoning && setExpanded(!expanded)}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
          reasoning ? 'hover:bg-white/5 cursor-pointer' : 'cursor-default'
        )}
      >
        {icon && <div className="text-indigo-400">{icon}</div>}
        <div className="flex-1">
          <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
          <div className="text-lg font-bold text-white mt-0.5">{value}</div>
        </div>
        {reasoning && (
          <div className="text-gray-600">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        )}
      </button>

      {expanded && reasoning && (
        <div className="px-4 pb-4 border-t border-[#1f2937] bg-black/20 animate-fade-in">
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-3 mb-2">Reasoning Breakdown</div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(reasoning).map(([key, val]) => (
              <div key={key} className="flex justify-between items-center py-1">
                <span className="text-xs text-gray-400 capitalize">{key.replace(/_/g, ' ')}</span>
                <span className="text-xs font-semibold text-white">{val}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

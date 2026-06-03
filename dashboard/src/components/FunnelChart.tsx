import { ConfidenceBadge } from './ConfidenceBadge';

interface FunnelStage {
  stage: string;
  count: number;
  confidence: number;
}

interface FunnelChartProps {
  stages: FunnelStage[];
  conversionRate: number;
}

export function FunnelChart({ stages, conversionRate }: FunnelChartProps) {
  const maxCount = stages[0]?.count ?? 1;

  return (
    <div className="space-y-3">
      {stages.map((stage, idx) => {
        const width = (stage.count / maxCount) * 100;
        const dropoff = idx > 0
          ? (((stages[idx - 1].count - stage.count) / stages[idx - 1].count) * 100).toFixed(1)
          : null;

        return (
          <div key={stage.stage} className="relative">
            {/* Drop-off label */}
            {dropoff && (
              <div className="flex items-center gap-2 mb-1 ml-2">
                <div className="w-px h-3 bg-red-500/40 ml-4" />
                <span className="text-xs text-red-400 font-medium">-{dropoff}% drop-off</span>
              </div>
            )}

            {/* Funnel bar */}
            <div className="flex items-center gap-3">
              <div
                className="relative flex-1 h-11 rounded-lg overflow-hidden transition-all duration-700"
                style={{ maxWidth: `${width}%`, minWidth: '20%' }}
              >
                {/* Background gradient bar */}
                <div
                  className="absolute inset-0 rounded-lg"
                  style={{
                    background: `linear-gradient(90deg, 
                      hsl(${230 - idx * 20}, 70%, ${55 - idx * 5}%) 0%, 
                      hsl(${230 - idx * 20}, 60%, ${45 - idx * 5}%) 100%)`,
                    opacity: 1 - idx * 0.1,
                  }}
                />
                {/* Stage name and count */}
                <div className="absolute inset-0 flex items-center justify-between px-3">
                  <span className="text-sm font-semibold text-white truncate">{stage.stage}</span>
                  <span className="text-sm font-bold text-white/90 ml-2">{stage.count.toLocaleString()}</span>
                </div>
              </div>

              {/* Confidence badge */}
              <ConfidenceBadge confidence={stage.confidence} />

              {/* Percentage of total */}
              <span className="text-sm text-gray-400 w-12 text-right">
                {((stage.count / maxCount) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        );
      })}

      {/* Overall conversion */}
      <div className="mt-4 pt-4 border-t border-[#1f2937] flex items-center justify-between">
        <span className="text-sm text-gray-400">Overall Conversion Rate</span>
        <span className="text-2xl font-bold text-indigo-400">{(conversionRate * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}

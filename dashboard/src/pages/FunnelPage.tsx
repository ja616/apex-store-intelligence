import { useState, useEffect, useCallback } from 'react';
import { TrendingDown } from 'lucide-react';
import {
  XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, AreaChart, Area, Line
} from 'recharts';
import { api } from '../lib/api';
import { FunnelChart } from '../components/FunnelChart';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

// Simulated historical comparison data
const historicalData = [
  { day: 'Mon', current: 0.28, previous: 0.31 },
  { day: 'Tue', current: 0.32, previous: 0.29 },
  { day: 'Wed', current: 0.35, previous: 0.33 },
  { day: 'Thu', current: 0.31, previous: 0.35 },
  { day: 'Fri', current: 0.38, previous: 0.36 },
  { day: 'Sat', current: 0.42, previous: 0.39 },
  { day: 'Sun', current: 0.34, previous: 0.32 },
];

const stageDescriptions: Record<string, string> = {
  entered: "Baseline store entrance traffic. Verified via CAM1 entry gate tracking.",
  browsed: "Shoppers who traversed aisles (CAM2/CAM3) and lingered for over 2 minutes.",
  billing_zone: "Shoppers who entered checkout lanes (CAM4/CAM5). Abandonment indicates queue exit.",
  purchased: "POS transactions attributed to visits via temporal correlation. Staff excluded.",
};

export function FunnelPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getFunnel>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getFunnel();
      setData(result);
      setError(null);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : 'Unknown connection error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return <div className="p-6 text-gray-400 text-sm">Loading funnel data...</div>;

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <TrendingDown size={24} />
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch conversion funnel metrics.
          </p>
          <button 
            onClick={() => { setLoading(true); setError(null); loadData(); }} 
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const stages = data!.stages;
  const entryCount = stages[0]?.count ?? 1;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Conversion Funnel</h2>
          <p className="text-xs text-gray-500 mt-0.5">Stage-by-stage visitor journey analysis</p>
        </div>
        <ConfidenceBadge confidence={data!.funnel_confidence} size="md" />
      </div>

      {/* Main Funnel */}
      <div className="card p-6">
        <FunnelChart stages={stages} conversionRate={data!.conversion_rate} />
      </div>

      {/* Stage breakdown cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {stages.map((stage, idx) => {
          const pct = (stage.count / entryCount) * 100;
          const dropoff = idx > 0 ? stages[idx - 1].count - stage.count : 0;
          const dropoffPct = idx > 0 ? ((dropoff / stages[idx - 1].count) * 100) : 0;

          return (
            <div key={stage.stage} className="card p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Stage {idx + 1}</span>
                  <ConfidenceBadge confidence={stage.confidence} />
                </div>
                <div className="text-2xl font-bold text-white mb-0.5">{stage.count.toLocaleString()}</div>
                <div className="text-xs font-semibold text-zinc-400 capitalize mb-2">{stage.stage.replace('_', ' ')}</div>
                
                {/* Progress bar */}
                <div className="h-1 bg-zinc-800 rounded-full overflow-hidden mb-3">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                
                <p className="text-xs text-zinc-400 leading-relaxed font-normal">{stageDescriptions[stage.stage] || stage.stage}</p>
              </div>

              <div className="flex items-center justify-between text-xs pt-4 border-t border-border mt-4">
                <span className="text-zinc-500">{pct.toFixed(0)}% of entry</span>
                {idx > 0 && (
                  <span className="flex items-center gap-1 text-rose-400 font-semibold">
                    <TrendingDown size={10} />
                    -{dropoffPct.toFixed(0)}% Drop
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Historical comparison */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Weekly Conversion Comparison</h3>
            <p className="text-xs text-gray-500 mt-0.5">This week vs last week conversion rate</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 bg-indigo-500 rounded" />
              <span className="text-gray-400">This Week</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 bg-gray-500 rounded border-dashed" style={{ borderStyle: 'dashed' }} />
              <span className="text-gray-400">Last Week</span>
            </div>
          </div>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="currentGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7b2cb1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#7b2cb1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af', fontSize: 12 }}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(v: any) => [`${(Number(v ?? 0) * 100).toFixed(1)}%`]}
              />
              <Area type="monotone" dataKey="current" stroke="#7b2cb1" fill="url(#currentGrad)" strokeWidth={2} name="This Week" />
              <Line type="monotone" dataKey="previous" stroke="#4b5563" strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="Last Week" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

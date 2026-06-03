import { useState, useEffect, useCallback } from 'react';
import { ArrowRight } from 'lucide-react';
import { api } from '../lib/api';
import { formatDuration, formatPct, cn } from '../lib/utils';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, Cell } from 'recharts';

const pathColors = ['#7c3aed', '#ec4899', '#d4af37', '#a78bfa', '#f43f5e'];

const zoneDisplayNames: Record<string, string> = {
  'Entry': 'Entry',
  'entry': 'Entry',
  'Floor A': 'Skincare Aisle',
  'floor-a': 'Skincare Aisle',
  'Floor B': 'Makeup Aisle',
  'floor-b': 'Makeup Aisle',
  'Billing A': 'Billing Counter',
  'billing-a': 'Billing Counter',
  'Billing B': 'Billing Counter',
  'billing-b': 'Billing Counter',
  'Exit': 'Exit',
  'exit': 'Exit',
};

const getZoneDisplayName = (name: string) => zoneDisplayNames[name] || name;

export function JourneysPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getJourneys>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getJourneys();
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

  if (loading) return <div className="p-6 text-gray-400 text-sm">Loading journey data...</div>;

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-git-branch"><line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch visitor journeys.
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

  const rawJourneys = data?.journeys || [];
  const journeys = rawJourneys.map((j: any, i) => ({
    journey_id: (j.journey_id || `j-${i}`) as string,
    path: (j.zones ?? j.path ?? []) as string[],
    visitor_count: (j.count ?? j.visitor_count ?? 0) as number,
    avg_duration_seconds: (j.avg_dwell_seconds ?? j.avg_duration_seconds ?? 0) as number,
    conversion_rate: (j.conversion_rate ?? 0) as number,
    avg_confidence: (j.confidence ?? j.avg_confidence ?? 0.5) as number,
  }));

  const totalJourneys = (data as any).total_journeys ?? journeys.reduce((sum, j) => sum + j.visitor_count, 0);

  const maxVisitors = journeys.length > 0 ? Math.max(...journeys.map((j) => j.visitor_count)) : 1;

  const barData = journeys.map((j, i) => ({
    name: `Path ${i + 1}`,
    visitors: j.visitor_count,
    conversion: Math.round(j.conversion_rate * 100),
    path: j.path.join(' → '),
  }));

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Visitor Journey Explorer</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {totalJourneys} total journeys recorded · Top 5 most common paths
          </p>
        </div>
      </div>

      {/* Journey flow visualization */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-white mb-6">Journey Flow Analysis</h3>

        {/* Sankey-style flow */}
        <div className="overflow-x-auto">
          <div className="flex items-stretch gap-0 min-w-[600px]" style={{ minHeight: 280 }}>
            {/* Zone columns */}
            {['Entry', 'Floor A/B', 'Billing', 'Exit'].map((zone, zIdx) => (
              <div key={zone} className="flex-1 flex flex-col items-center gap-2">
                {/* Zone header */}
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">{zone}</div>

                {/* Flows */}
                {journeys.map((j, jIdx) => {
                  const relevantZones = j.path.filter((p) => {
                    if (zIdx === 0) return p === 'Entry';
                    if (zIdx === 1) return p.startsWith('Floor');
                    if (zIdx === 2) return p.startsWith('Billing');
                    if (zIdx === 3) return p === 'Exit';
                    return false;
                  });
                  if (relevantZones.length === 0) return null;

                  const width = (j.visitor_count / maxVisitors) * 100;

                  return (
                    <div
                      key={jIdx}
                      className="rounded-md flex items-center justify-center text-xs font-semibold text-white transition-all hover:opacity-90"
                      style={{
                        width: `${Math.max(40, width)}%`,
                        height: 32,
                        background: pathColors[jIdx],
                        opacity: 0.6 + jIdx * 0.08,
                      }}
                      title={`${j.visitor_count} visitors`}
                    >
                      {j.visitor_count}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-[#1f2937]">
          {journeys.map((j, i) => (
            <div key={j.journey_id} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: pathColors[i] }} />
              <span className="text-xs text-gray-400">{j.path.map(getZoneDisplayName).join(' → ')}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Journey cards */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-white">Top Journey Paths</h3>
        {journeys.map((journey, idx) => (
          <div key={journey.journey_id} className="card p-5">
            <div className="flex items-start gap-4">
              {/* Rank */}
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                style={{ background: pathColors[idx] }}
              >
                {idx + 1}
              </div>

              <div className="flex-1 min-w-0">
                {/* Path visualization */}
                <div className="flex items-center flex-wrap gap-1 mb-3">
                  {journey.path.map((step, sIdx) => (
                    <div key={sIdx} className="flex items-center gap-1">
                      <span
                        className="text-xs font-semibold px-2 py-1 rounded-md text-white"
                        style={{ background: `${pathColors[idx]}20`, border: `1px solid ${pathColors[idx]}40` }}
                      >
                        {getZoneDisplayName(step)}
                      </span>
                      {sIdx < journey.path.length - 1 && (
                        <ArrowRight size={10} className="text-zinc-500" />
                      )}
                    </div>
                  ))}
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 mb-0.5">Visitors</div>
                    <div className="text-lg font-bold text-white">{journey.visitor_count}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-0.5">Avg Duration</div>
                    <div className="text-lg font-bold text-white">{formatDuration(journey.avg_duration_seconds)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-0.5">Conversion Rate</div>
                    <div className={cn(
                      'text-lg font-bold',
                      journey.conversion_rate > 0.7 ? 'text-green-400' :
                      journey.conversion_rate > 0.3 ? 'text-amber-400' : 'text-gray-400'
                    )}>
                      {journey.conversion_rate > 0 ? formatPct(journey.conversion_rate) : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-0.5">Avg Confidence</div>
                    <ConfidenceBadge confidence={journey.avg_confidence} size="md" />
                  </div>
                </div>

                {/* Visitor proportion bar */}
                <div className="mt-3">
                  <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(journey.visitor_count / maxVisitors) * 100}%`,
                        background: pathColors[idx],
                      }}
                    />
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    {totalJourneys > 0 ? ((journey.visitor_count / totalJourneys) * 100).toFixed(1) : '0.0'}% of all journeys
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison chart */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Journey Comparison</h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="left" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={35} />
              <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => `${v}%`} tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af', fontSize: 12 }}
              />
              <Bar yAxisId="left" dataKey="visitors" radius={[4, 4, 0, 0]} name="Visitors">
                {barData.map((_, i) => <Cell key={i} fill={pathColors[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

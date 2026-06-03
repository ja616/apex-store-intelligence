import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { ZoneHeatmap } from '../components/ZoneHeatmap';
import { formatDuration } from '../lib/utils';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, Cell } from 'recharts';

export function HeatmapPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getHeatmap>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getHeatmap();
      setData(result);
      setError(null);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : 'Unknown connection error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 20000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) return <div className="p-6 text-gray-400 text-sm">Loading heatmap data...</div>;

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-map"><path d="M14.106 5.553a2 2 0 0 0-1.602 0L7.894 7.447a2 2 0 0 1-1.578 0l-2.73-1.09A1 1 0 0 0 2.22 7.29v11.287a1 1 0 0 0 .587.906l3.707 1.482a2 2 0 0 0 1.602 0l4.61-1.894a2 2 0 0 1 1.578 0l2.73 1.09a1 1 0 0 0 1.366-.92V7.29a1 1 0 0 0-.587-.906l-3.707-1.482z"/><path d="M8 7v13"/><path d="M16 4v13"/></svg>
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch store heatmap metrics.
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

  const zones = data!.zones;
  const zoneBarData = zones.map((z) => {
    const visits = (z as any).visit_count ?? (z as any).visitor_count ?? 0;
    const density = (z as any).traffic_density ?? ((z as any).occupancy_pct ? (z as any).occupancy_pct * 100 : 0);
    return {
      name: z.zone_name,
      dwell: Math.round(z.avg_dwell_seconds / 60),
      visitors: visits,
      occupancy: Math.round(density),
    };
  });

  const occupancyColors = zones.map((z) => {
    const score = (z as any).traffic_density ?? ((z as any).occupancy_pct ? (z as any).occupancy_pct * 100 : 0);
    if (score < 40) return 'rgba(124, 58, 237, 0.3)';
    if (score < 65) return 'rgba(124, 58, 237, 0.6)';
    if (score < 85) return 'rgba(124, 58, 237, 0.85)';
    return '#7c3aed';
  });

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Store Heatmap</h2>
          <p className="text-xs text-gray-500 mt-0.5">Zone occupancy and traffic density · Updates every 20s</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400 font-medium">LIVE</span>
        </div>
      </div>

      {/* Main heatmap */}
      <div className="card p-6">
        <ZoneHeatmap zones={zones} />
      </div>

      {/* Zone statistics */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Visitor count by zone */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Visitor Count by Zone</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={zoneBarData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af', fontSize: 12 }}
                  itemStyle={{ color: '#7b2cb1' }}
                />
                <Bar dataKey="visitors" radius={[4, 4, 0, 0]}>
                  {zoneBarData.map((_, i) => (
                    <Cell key={i} fill={occupancyColors[i]} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Avg dwell by zone */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Average Dwell Time (minutes)</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={zoneBarData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af', fontSize: 12 }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(v: any) => [`${v ?? 0} min`]}
                />
                <Bar dataKey="dwell" fill="#10b981" radius={[4, 4, 0, 0]} fillOpacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Zone detail table */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1f2937]">
          <h3 className="text-sm font-semibold text-white">Zone Statistics</h3>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              {['Zone', 'Camera', 'Visit Frequency', 'Average Dwell', 'Attention Score', 'Confidence'].map((h) => (
                <th key={h} className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((zone, idx) => {
              const visits = (zone as any).visit_count ?? (zone as any).visitor_count ?? 0;
              const density = (zone as any).traffic_density ?? ((zone as any).occupancy_pct ? (zone as any).occupancy_pct * 100 : 0);
              const conf = (zone as any).confidence ?? 0.92;
              return (
                <tr key={zone.zone_id} className="border-b border-border/50 hover:bg-white/3 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-white">{zone.zone_name}</td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-400">{zone.camera_id}</td>
                  <td className="px-4 py-3 text-sm text-gray-300">{visits}</td>
                  <td className="px-4 py-3 text-sm text-gray-300">{formatDuration(zone.avg_dwell_seconds)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${density}%`, background: occupancyColors[idx] }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-8">{Math.round(density)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBadge confidence={conf} size="sm" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { Shield, Users, RotateCcw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, Cell } from 'recharts';
import { api } from '../lib/api';
import { formatRelativeTime, cn } from '../lib/utils';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

// Confidence distribution histogram data
const confidenceDistribution = [
  { range: '0-50%', count: 3, color: '#ef4444' },
  { range: '50-65%', count: 8, color: '#f59e0b' },
  { range: '65-75%', count: 22, color: '#f59e0b' },
  { range: '75-85%', count: 48, color: '#10b981' },
  { range: '85-95%', count: 89, color: '#10b981' },
  { range: '95-100%', count: 242, color: '#10b981' },
];

export function IdentityPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getIdentity>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getIdentity();
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

  if (loading) return <div className="p-6 text-gray-400 text-sm">Loading identity data...</div>;

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <Shield size={24} />
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch visitor identities.
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

  const d = data!;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Identity Confidence Monitor</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Identity matching, re-entry detection, and staff exclusion log
          </p>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
              <Shield size={14} className="text-indigo-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Total Identities</span>
          </div>
          <div className="text-3xl font-bold text-white">{d.total_identities}</div>
          <div className="text-xs text-gray-500 mt-1">Unique individuals tracked</div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <RotateCcw size={14} className="text-amber-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Re-Entries</span>
          </div>
          <div className="text-3xl font-bold text-amber-400">{d.reentry_count}</div>
          <div className="text-xs text-gray-500 mt-1">Visitors who returned today</div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Users size={14} className="text-purple-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Staff Excluded</span>
          </div>
          <div className="text-3xl font-bold text-purple-400">{d.staff_excluded}</div>
          <div className="text-xs text-gray-500 mt-1">Staff excluded from counts</div>
        </div>
      </div>

      {/* Confidence distribution histogram */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Identity Confidence Distribution</h3>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={confidenceDistribution} barSize={32}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="range" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af', fontSize: 12 }}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(v: any) => [v ?? 0, 'Identities']}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {confidenceDistribution.map((entry, i) => (
                  <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Identity table */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1f2937]">
          <h3 className="text-sm font-semibold text-white">Identity Match Log</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#1f2937]">
                {['Identity', 'Matched Sessions', 'Matching Explanation', 'Re-Entry', 'Confidence', 'Last Seen'].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.identities.map((identity, idx) => (
                <tr
                  key={identity.identity_id}
                  className={cn(
                    'border-b border-[#1f2937]/50 hover:bg-white/3 transition-colors',
                    idx % 2 === 0 ? '' : 'bg-white/[0.01]'
                  )}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold',
                        (identity as any).is_staff ? 'bg-purple-500/20 text-purple-400' : 'bg-indigo-500/20 text-indigo-400'
                      )}>
                        {(identity as any).is_staff ? 'S' : 'I'}
                      </div>
                      <span className="text-sm font-mono text-white">{identity.identity_id}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {identity.matched_visitors.map((v) => (
                        <span key={v} className="text-xs font-mono bg-indigo-500/10 text-indigo-300 px-1.5 py-0.5 rounded">
                          {v}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-400">{identity.matching_explanation}</span>
                  </td>
                  <td className="px-4 py-3">
                    {identity.is_reentry ? (
                      <div>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                          <RotateCcw size={9} />
                          RE-ENTRY
                        </span>
                        <div className="text-xs text-gray-500 mt-0.5">+{identity.reentry_gap_minutes}min gap</div>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBadge confidence={identity.reentry_confidence} />
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-400">{formatRelativeTime(identity.last_seen)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Re-entry events timeline */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Re-Entry Events Timeline</h3>
        <div className="space-y-3">
          {d.identities
            .filter((i) => i.is_reentry)
            .map((identity) => (
              <div key={identity.identity_id} className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-amber-400 mt-1.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-mono text-white">{identity.identity_id}</span>
                    <span className="text-xs text-gray-500">re-entered after {identity.reentry_gap_minutes} min gap</span>
                    <ConfidenceBadge confidence={identity.reentry_confidence} />
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">{identity.matching_explanation}</div>
                </div>
                <span className="text-xs text-gray-500 flex-shrink-0">{formatRelativeTime(identity.last_seen)}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

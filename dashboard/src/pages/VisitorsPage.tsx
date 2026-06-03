import { useState, useEffect, useCallback } from 'react';
import { Users, Search, Filter } from 'lucide-react';
import { api } from '../lib/api';
import { formatDuration, formatRelativeTime, cn } from '../lib/utils';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

type ConfidenceFilter = 'all' | 'high' | 'medium' | 'low';

export function VisitorsPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getVisitors>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ConfidenceFilter>('all');
  const [search, setSearch] = useState('');
  const [showStaff, setShowStaff] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getVisitors();
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
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <Users size={24} />
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch visitor metrics.
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

  const filteredVisitors = data?.visitors.filter((v) => {
    if (!showStaff && v.is_staff) return false;
    if (search && !v.visitor_id.toLowerCase().includes(search.toLowerCase())) return false;
    if (filter === 'high' && v.confidence < 0.85) return false;
    if (filter === 'medium' && (v.confidence < 0.65 || v.confidence >= 0.85)) return false;
    if (filter === 'low' && v.confidence >= 0.65) return false;
    return true;
  }) ?? [];

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white">Live Visitor Metrics</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {data?.total_active ?? '--'} active visitors · {data?.staff_active ?? '--'} staff · Polling every 15s
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400 font-medium">LIVE</span>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3 items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-40">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search visitor ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 bg-[#0a0b14] border border-[#1f2937] rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500/50"
          />
        </div>

        {/* Confidence filter */}
        <div className="flex items-center gap-1 bg-[#0a0b14] border border-[#1f2937] rounded-lg p-1">
          {(['all', 'high', 'medium', 'low'] as ConfidenceFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-all',
                filter === f
                  ? 'bg-indigo-500 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Staff toggle */}
        <button
          onClick={() => setShowStaff(!showStaff)}
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border transition-all',
            showStaff
              ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-400'
              : 'border-[#1f2937] text-gray-400 hover:text-white'
          )}
        >
          <Filter size={12} />
          {showStaff ? 'Showing Staff' : 'Staff Hidden'}
        </button>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#1f2937]">
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Visitor ID</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Camera</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Current Zone</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Dwell Time</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">First Seen</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Confidence</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3">Type</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-gray-500 text-sm">
                    Loading visitors...
                  </td>
                </tr>
              ) : filteredVisitors.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-gray-500 text-sm">
                    No visitors match the current filters
                  </td>
                </tr>
              ) : (
                filteredVisitors.map((visitor, idx) => (
                  <tr
                    key={visitor.visitor_id}
                    className={cn(
                      'border-b border-[#1f2937]/50 transition-colors hover:bg-white/3',
                      idx % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.01]'
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold',
                          visitor.is_staff ? 'bg-purple-500/20 text-purple-400' : 'bg-indigo-500/20 text-indigo-400'
                        )}>
                          {visitor.is_staff ? 'S' : 'V'}
                        </div>
                        <span className="text-sm font-mono text-white">{visitor.visitor_id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-300 font-mono">{visitor.camera_id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-200">{visitor.zone}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-300">{formatDuration(visitor.dwell_seconds)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-400">{formatRelativeTime(visitor.entered_at)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceBadge confidence={visitor.confidence} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      {visitor.is_staff ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30">
                          STAFF
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                          VISITOR
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[#1f2937] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users size={14} className="text-gray-500" />
            <span className="text-xs text-gray-500">
              Showing {filteredVisitors.length} of {data?.visitors.length ?? 0} visitors
            </span>
          </div>
          <button
            onClick={loadData}
            className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Refresh ↻
          </button>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from 'recharts';
import { api } from '../lib/api';
import { formatRelativeTime, cn } from '../lib/utils';
import { AnomalyBadge } from '../components/AnomalyBadge';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

type SeverityFilter = 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW';

// Simulated timeline data
const timelineData = [
  { time: '9am', HIGH: 0, MEDIUM: 1, LOW: 0 },
  { time: '10am', HIGH: 1, MEDIUM: 0, LOW: 1 },
  { time: '11am', HIGH: 0, MEDIUM: 2, LOW: 0 },
  { time: '12pm', HIGH: 2, MEDIUM: 1, LOW: 2 },
  { time: '1pm', HIGH: 1, MEDIUM: 3, LOW: 1 },
  { time: '2pm', HIGH: 3, MEDIUM: 2, LOW: 0 },
  { time: '3pm', HIGH: 2, MEDIUM: 1, LOW: 3 },
  { time: '4pm', HIGH: 4, MEDIUM: 2, LOW: 1 },
  { time: 'Now', HIGH: 2, MEDIUM: 2, LOW: 1 },
];

export function AnomaliesPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getAnomalies>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<SeverityFilter>('ALL');
  const [expanded, setExpanded] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getAnomalies();
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
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <AlertTriangle size={24} />
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch store anomalies.
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

  const filtered = data?.anomalies.filter(
    (a) => filter === 'ALL' || a.severity === filter
  ) ?? [];

  const severityCounts = {
    ALL: data?.anomalies.length ?? 0,
    HIGH: data?.anomalies.filter((a) => a.severity === 'HIGH').length ?? 0,
    MEDIUM: data?.anomalies.filter((a) => a.severity === 'MEDIUM').length ?? 0,
    LOW: data?.anomalies.filter((a) => a.severity === 'LOW').length ?? 0,
  };

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Anomaly Center</h2>
          <p className="text-xs text-gray-500 mt-0.5">Active alerts requiring attention</p>
        </div>
        <div className="flex items-center gap-2">
          {data && data.total_active > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/30 rounded-full">
              <AlertTriangle size={12} className="text-red-400" />
              <span className="text-xs font-semibold text-red-400">{data.total_active} ACTIVE</span>
            </div>
          )}
        </div>
      </div>

      {/* Timeline chart */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold text-white mb-4">Anomaly Timeline (Today)</h3>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timelineData}>
              <defs>
                <linearGradient id="highGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="medGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="lowGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={25} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af', fontSize: 12 }}
              />
              <Area type="monotone" dataKey="HIGH" stroke="#ef4444" fill="url(#highGrad)" strokeWidth={2} name="High" />
              <Area type="monotone" dataKey="MEDIUM" stroke="#f59e0b" fill="url(#medGrad)" strokeWidth={2} name="Medium" />
              <Area type="monotone" dataKey="LOW" stroke="#3b82f6" fill="url(#lowGrad)" strokeWidth={2} name="Low" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Severity filter tabs */}
      <div className="flex items-center gap-2">
        {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as SeverityFilter[]).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold border transition-all',
              filter === s ? (
                s === 'HIGH' ? 'border-red-500/40 bg-red-500/15 text-red-400' :
                s === 'MEDIUM' ? 'border-amber-500/40 bg-amber-500/15 text-amber-400' :
                s === 'LOW' ? 'border-blue-500/40 bg-blue-500/15 text-blue-400' :
                'border-indigo-500/40 bg-indigo-500/15 text-indigo-400'
              ) : 'border-[#1f2937] text-gray-400 hover:text-white'
            )}
          >
            {s}
            <span className={cn(
              'min-w-[18px] h-[18px] rounded-full text-[10px] flex items-center justify-center font-bold',
              filter === s ? 'bg-current/20' : 'bg-[#1f2937] text-gray-500'
            )}>
              {severityCounts[s]}
            </span>
          </button>
        ))}
      </div>

      {/* Anomaly list */}
      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-gray-500 text-sm">Loading anomalies...</div>
        ) : filtered.length === 0 ? (
          <div className="card p-12 text-center">
            <AlertTriangle size={32} className="text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">No anomalies for this severity level</p>
          </div>
        ) : (
          filtered.map((anomaly) => {
            const isExp = expanded === anomaly.anomaly_id;
            return (
              <div key={anomaly.anomaly_id} className="card overflow-hidden">
                <button
                  className="w-full flex items-start gap-4 p-5 hover:bg-white/3 transition-colors text-left"
                  onClick={() => setExpanded(isExp ? null : anomaly.anomaly_id)}
                >
                  {/* Severity indicator */}
                  <div className={cn(
                    'w-1 self-stretch rounded-full flex-shrink-0',
                    anomaly.severity === 'HIGH' ? 'bg-red-500' :
                    anomaly.severity === 'MEDIUM' ? 'bg-amber-500' : 'bg-blue-500'
                  )} />

                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-sm font-semibold text-white">{anomaly.anomaly_type.replace(/_/g, ' ')}</span>
                      <AnomalyBadge severity={anomaly.severity} />
                      <ConfidenceBadge confidence={anomaly.confidence} />
                    </div>
                    <p className="text-sm text-gray-400 mb-2">{anomaly.reason}</p>
                    <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
                      <span className="font-mono">{anomaly.camera_id}</span>
                      <span>{formatRelativeTime(anomaly.detected_at)}</span>
                    </div>
                  </div>

                  <div className="flex-shrink-0 text-gray-600">
                    {isExp ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </button>

                {/* Expanded content */}
                {isExp && (
                  <div className="px-5 pb-5 border-t border-[#1f2937] bg-black/20 animate-fade-in">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                      <div>
                        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Suggested Action</div>
                        <p className="text-sm text-emerald-400 font-medium">{anomaly.suggested_action}</p>
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Detection Rule</div>
                        <code className="text-xs text-indigo-300 font-mono bg-indigo-500/10 px-3 py-2 rounded-lg block">
                          {anomaly.detection_rule}
                        </code>
                      </div>
                    </div>
                    <div className="mt-4">
                      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Anomaly ID</div>
                      <span className="text-xs font-mono text-gray-500">{anomaly.anomaly_id}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

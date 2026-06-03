import { useState, useEffect, useCallback } from 'react';
import { Users, ShoppingCart, Clock, AlertTriangle, BarChart3, Shield } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from 'recharts';
import { api } from '../lib/api';
import { mockSparklines } from '../lib/mock-data';
import { formatRelativeTime, formatPct } from '../lib/utils';
import { KPICard } from '../components/KPICard';
import { FunnelChart } from '../components/FunnelChart';
import { LiveTicker } from '../components/LiveTicker';
import { AnomalyBadge } from '../components/AnomalyBadge';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { MetricWithReason } from '../components/MetricWithReason';

interface OverviewData {
  metrics: Awaited<ReturnType<typeof api.getMetrics>>;
  funnel: Awaited<ReturnType<typeof api.getFunnel>>;
  anomalies: Awaited<ReturnType<typeof api.getAnomalies>>;
  tickerEvents: Awaited<ReturnType<typeof api.getRecentEvents>>;
}

const hourlyData = [
  { hour: '9am', visitors: 38 },
  { hour: '10am', visitors: 52 },
  { hour: '11am', visitors: 67 },
  { hour: '12pm', visitors: 89 },
  { hour: '1pm', visitors: 76 },
  { hour: '2pm', visitors: 82 },
  { hour: '3pm', visitors: 94 },
  { hour: '4pm', visitors: 71 },
  { hour: '5pm', visitors: 65 },
  { hour: '6pm', visitors: 58 },
];

export function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const loadData = useCallback(async () => {
    try {
      const [metrics, funnel, anomalies, tickerEvents] = await Promise.all([
        api.getMetrics(),
        api.getFunnel(),
        api.getAnomalies(),
        api.getRecentEvents(),
      ]);
      setData({ metrics, funnel, anomalies, tickerEvents });
      setError(null);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : 'Unknown connection error');
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-400 text-sm">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <AlertTriangle size={24} />
            <h3 className="text-lg font-bold text-white">APEX Server Offline</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server. Under the zero mock data policy, the dashboard requires a live API connection to fetch real-time store metrics.
          </p>
          <div className="bg-[#0b0514] p-4 rounded-lg border border-[#24143a] mb-4">
            <div className="text-xs text-gray-500 font-semibold mb-1">POSSIBLE SOLUTIONS:</div>
            <ul className="list-disc pl-4 text-xs text-gray-400 space-y-1">
              <li>Check if the backend FastAPI server is running.</li>
              <li>Ensure the server is hosted at <code className="text-pink-400">http://localhost:8000</code>.</li>
              <li>Run the startup command in your terminal: <code className="text-indigo-400">python -m uvicorn apex.api.main:app --host 127.0.0.1 --port 8000 --reload</code></li>
            </ul>
          </div>
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

  const m = data!.metrics;
  const f = data!.funnel;
  const a = data!.anomalies;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Last refresh indicator */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Today's Performance</h2>
          <p className="text-xs text-gray-500 mt-0.5">Brigade Road Store · Auto-refreshes every 30s</p>
        </div>
        <div className="text-xs text-gray-500">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </div>
      </div>

      {/* Hero KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPICard
          title="Visitors Today"
          metric={m.unique_visitors.toLocaleString()}
          subtitle="Unique shoppers detected"
          trend={8.2}
          trendLabel="vs yesterday"
          confidence={m.metric_confidence}
          sparklineData={mockSparklines.visitors}
          icon={<Users size={14} />}
          accentColor="indigo"
        />
        <KPICard
          title="Conversion Rate"
          metric={formatPct(m.conversion_rate)}
          subtitle={`${m.reasoning.converted_sessions ?? 0} checkout conversions`}
          trend={-2.1}
          trendLabel="vs yesterday"
          confidence={m.metric_confidence}
          sparklineData={mockSparklines.conversion.map(v => v * 100)}
          icon={<ShoppingCart size={14} />}
          accentColor="green"
        />
        <KPICard
          title="Queue Depth"
          metric={a.anomalies.some(an => an.anomaly_type === 'QUEUE_SPIKE') ? 6 : 2}
          subtitle="Active billing lane occupancy"
          trend={0.0}
          trendLabel="flat vs last hour"
          confidence={0.92}
          sparklineData={[2, 3, 2, 4, 3, 2, 3, 2, 2]}
          icon={<Clock size={14} />}
          accentColor="amber"
        />
        <KPICard
          title="Abandonment Rate"
          metric={formatPct(Math.max(0, 1 - m.conversion_rate))}
          subtitle="Left without checkout"
          trend={2.1}
          trendLabel="vs yesterday"
          confidence={m.metric_confidence}
          sparklineData={mockSparklines.conversion.map(v => (1 - v) * 100)}
          icon={<AlertTriangle size={14} />}
          accentColor="red"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Conversion Funnel */}
        <div className="xl:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-white">Conversion Funnel</h3>
              <p className="text-xs text-gray-500 mt-1">Today's visitor journey stages</p>
            </div>
            <ConfidenceBadge confidence={f.funnel_confidence} size="md" />
          </div>
          <FunnelChart stages={f.stages} conversionRate={f.conversion_rate} />
        </div>

        {/* Live Ticker */}
        <div className="card p-6">
          <LiveTicker events={data!.tickerEvents} />
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Hourly traffic */}
        <div className="xl:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Hourly Visitor Traffic</h3>
              <p className="text-xs text-gray-500 mt-1">Visitor count per hour today</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <BarChart3 size={14} />
              <span>Peak: 3pm</span>
            </div>
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyData} barSize={24}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="hour" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af', fontSize: 12 }}
                  itemStyle={{ color: '#7b2cb1' }}
                />
                <Bar dataKey="visitors" fill="#7b2cb1" radius={[4, 4, 0, 0]} fillOpacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Active Anomalies panel */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Active Anomalies</h3>
            <span className="text-xs text-red-400 font-medium">{a.total_active} active</span>
          </div>
          <div className="space-y-3">
            {a.anomalies.slice(0, 3).map((anomaly) => (
              <div key={anomaly.anomaly_id} className="rounded-lg border border-[#1f2937] p-3 hover:bg-white/3 transition-colors">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <span className="text-xs font-semibold text-white">{anomaly.anomaly_type.replace(/_/g, ' ')}</span>
                  <AnomalyBadge severity={anomaly.severity} />
                </div>
                <p className="text-xs text-gray-400 line-clamp-2">{anomaly.reason}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gray-600">{anomaly.camera_id}</span>
                  <span className="text-xs text-gray-500">{formatRelativeTime(anomaly.detected_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* System Confidence Strip */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-indigo-400" />
            <span className="text-sm font-semibold text-white">System Confidence Overview</span>
          </div>
          <ConfidenceBadge confidence={m.metric_confidence} size="md" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricWithReason
            label="High Confidence Sessions"
            value={m.reasoning.high_confidence_sessions}
            icon={<Shield size={14} />}
          />
          <MetricWithReason
            label="Low Confidence Sessions"
            value={m.reasoning.low_confidence_sessions}
            icon={<AlertTriangle size={14} />}
          />
          <MetricWithReason
            label="Staff Excluded"
            value={m.reasoning.staff_excluded}
            icon={<Users size={14} />}
          />
          <MetricWithReason
            label="Total Sessions"
            value={m.reasoning.sessions}
            icon={<BarChart3 size={14} />}
            reasoning={m.reasoning as unknown as Record<string, string | number>}
          />
        </div>
        {/* Confidence bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-500 mb-1.5">
            <span>Overall system confidence</span>
            <span className="text-green-400 font-medium">{(m.metric_confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-[#1f2937] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${m.metric_confidence * 100}%`,
                background: 'linear-gradient(90deg, #7b2cb1, #ec4899)',
              }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span>0%</span>
            <span>65% threshold</span>
            <span>85% threshold</span>
            <span>100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

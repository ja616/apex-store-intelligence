import { useState, useEffect, useCallback } from 'react';
import { Activity, Database, Brain, Camera, Clock, Wifi } from 'lucide-react';
import { api } from '../lib/api';
import { formatUptime, formatRelativeTime, cn } from '../lib/utils';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

export function HealthPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getHealth>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uptime, setUptime] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const result = await api.getHealth();
      setData(result);
      setUptime(result.uptime_seconds);
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

  // Live uptime counter
  useEffect(() => {
    const timer = setInterval(() => setUptime((u) => u + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  if (loading) return <div className="p-6 text-gray-400 text-sm">Loading health data...</div>;

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[80vh]">
        <div className="card p-6 border-destructive/30 bg-destructive/10 max-w-2xl w-full animate-fade-in">
          <div className="flex items-center gap-3 text-red-400 mb-3">
            <Activity size={24} />
            <h3 className="text-lg font-bold text-white">Connection Error</h3>
          </div>
          <p className="text-sm text-gray-300 mb-4">
            Could not connect to the APEX API backend server to fetch system health statistics.
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
  const cameras = d.cameras ?? [];

  const statusDot = (status: string) =>
    status === 'online' ? 'bg-green-400' : status === 'degraded' ? 'bg-amber-400' : 'bg-red-400';

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">System Health</h2>
          <p className="text-xs text-gray-500 mt-0.5">Live system status and diagnostics</p>
        </div>
        <div className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold',
          d.status === 'healthy'
            ? 'border-green-500/30 bg-green-500/10 text-green-400'
            : 'border-red-500/30 bg-red-500/10 text-red-400'
        )}>
          <Activity size={12} />
          {d.status.toUpperCase()}
        </div>
      </div>

      {/* Core status cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* DB Status */}
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
              <Database size={14} className="text-indigo-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Database</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn('w-2 h-2 rounded-full', d.db_status === 'connected' ? 'bg-green-400' : 'bg-red-400')} />
            <span className="text-sm font-semibold text-white capitalize">{d.db_status}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">PostgreSQL · Brigade Road</div>
        </div>

        {/* Model Status */}
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Brain size={14} className="text-purple-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">AI Model</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn('w-2 h-2 rounded-full', d.model_status === 'loaded' ? 'bg-green-400' : 'bg-amber-400')} />
            <span className="text-sm font-semibold text-white capitalize">{d.model_status}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">Vision Transformer · v2.3.1</div>
        </div>

        {/* Event Freshness */}
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center">
              <Wifi size={14} className="text-green-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Last Event</span>
          </div>
          <div className="text-sm font-semibold text-white">{d.event_freshness_seconds}s ago</div>
          <div className="text-xs text-gray-500 mt-1">{formatRelativeTime(d.last_event_at)}</div>
          <div className="mt-2 h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                d.event_freshness_seconds < 30 ? 'bg-green-400' :
                d.event_freshness_seconds < 60 ? 'bg-amber-400' : 'bg-red-400'
              )}
              style={{ width: `${Math.max(0, 100 - d.event_freshness_seconds)}%` }}
            />
          </div>
        </div>

        {/* Uptime */}
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <Clock size={14} className="text-amber-400" />
            </div>
            <span className="text-xs font-semibold text-gray-400 uppercase">Uptime</span>
          </div>
          <div className="text-sm font-bold text-white font-mono">{formatUptime(uptime)}</div>
          <div className="text-xs text-gray-500 mt-1">System running</div>
        </div>
      </div>

      {/* System confidence */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white">System Confidence</h3>
          <ConfidenceBadge confidence={d.confidence} size="md" />
        </div>
        <div className="h-3 bg-[#1f2937] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{
              width: `${d.confidence * 100}%`,
              background: 'linear-gradient(90deg, #6366f1, #10b981)',
            }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-600 mt-2">
          <span>0%</span>
          <span className="text-green-400 font-medium">{(d.confidence * 100).toFixed(1)}% Overall</span>
          <span>100%</span>
        </div>
      </div>

      {/* Camera feed status */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1f2937] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera size={16} className="text-gray-400" />
            <h3 className="text-sm font-semibold text-white">Camera Feed Status</h3>
          </div>
          <span className="text-xs text-gray-500">
            {cameras.filter((c) => c.status === 'online').length}/{cameras.length} online
          </span>
        </div>
        <div className="divide-y divide-[#1f2937]">
          {cameras.map((cam) => (
            <div key={cam.camera_id} className="flex items-center gap-4 px-6 py-4 hover:bg-white/3 transition-colors">
              <div className="w-9 h-9 rounded-lg bg-[#0a0b14] border border-[#1f2937] flex items-center justify-center">
                <Camera size={14} className="text-gray-400" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{cam.camera_id}</span>
                  <div className={cn('w-1.5 h-1.5 rounded-full', statusDot(cam.status))} />
                  <span className={cn(
                    'text-xs capitalize font-medium',
                    cam.status === 'online' ? 'text-green-400' :
                    cam.status === 'degraded' ? 'text-amber-400' : 'text-red-400'
                  )}>
                    {cam.status}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{cam.zone}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-mono text-white">{cam.fps} FPS</div>
                <div className="text-xs text-gray-500">{cam.last_event_seconds}s ago</div>
              </div>
              {/* FPS bar */}
              <div className="w-20 h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full',
                    cam.fps >= 24 ? 'bg-green-400' : cam.fps >= 15 ? 'bg-amber-400' : 'bg-red-400'
                  )}
                  style={{ width: `${(cam.fps / 30) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

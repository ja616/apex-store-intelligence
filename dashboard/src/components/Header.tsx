import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { RefreshCw, Wifi, WifiOff, Menu } from 'lucide-react';
import { cn, formatTime } from '../lib/utils';

const routeTitles: Record<string, string> = {
  '/': 'Executive Overview',
  '/visitors': 'Live Visitor Metrics',
  '/funnel': 'Conversion Funnel',
  '/heatmap': 'Store Heatmap',
  '/anomalies': 'Anomaly Center',
  '/health': 'System Health',
  '/journeys': 'Visitor Journey Explorer',
  '/identity': 'Identity Confidence Monitor',
};

interface HeaderProps {
  onToggleSidebar: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  systemHealthy?: boolean;
}

export function Header({ onToggleSidebar, onRefresh, isRefreshing, systemHealthy = true }: HeaderProps) {
  const location = useLocation();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const title = routeTitles[location.pathname] ?? 'Dashboard';

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-background flex-shrink-0">
      <div className="flex items-center gap-4">
        <button
          onClick={onToggleSidebar}
          className="text-gray-400 hover:text-white transition-colors p-1 rounded"
        >
          <Menu size={18} />
        </button>
        <div>
          <h1 className="text-sm font-semibold text-white">{title}</h1>
          <p className="text-xs text-gray-500">Brigade Road, Bangalore</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Clock */}
        <div className="text-xs font-mono text-gray-400 hidden sm:block">
          {formatTime(now.toISOString())}
        </div>

        {/* System status */}
        <div className={cn(
          'flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border',
          systemHealthy
            ? 'border-green-500/30 bg-green-500/10 text-green-400'
            : 'border-red-500/30 bg-red-500/10 text-red-400'
        )}>
          {systemHealthy ? <Wifi size={12} /> : <WifiOff size={12} />}
          <span className="font-medium">{systemHealthy ? 'LIVE' : 'OFFLINE'}</span>
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded hover:bg-white/5"
            title="Refresh data"
          >
            <RefreshCw size={16} className={cn(isRefreshing && 'animate-spin')} />
          </button>
        )}
      </div>
    </header>
  );
}

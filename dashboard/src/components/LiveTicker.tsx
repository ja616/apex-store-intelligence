import {} from 'react';
import { ArrowUpRight, ArrowDownLeft, AlertTriangle, ShoppingCart, ArrowRight } from 'lucide-react';
import { cn } from '../lib/utils';

interface TickerEvent {
  id: number;
  type: string;
  visitor_id: string;
  zone: string;
  time: string;
  confidence: number;
}

interface LiveTickerProps {
  events: TickerEvent[];
}

const eventConfig: Record<string, { icon: typeof ArrowUpRight; color: string; label: string }> = {
  ENTRY: { icon: ArrowUpRight, color: 'text-green-400', label: 'Entered' },
  EXIT: { icon: ArrowDownLeft, color: 'text-gray-400', label: 'Exited' },
  ZONE_CHANGE: { icon: ArrowRight, color: 'text-indigo-400', label: 'Moved to' },
  PURCHASE: { icon: ShoppingCart, color: 'text-emerald-400', label: 'Purchased at' },
  ANOMALY: { icon: AlertTriangle, color: 'text-red-400', label: 'Alert at' },
};

function TickerRow({ event }: { event: TickerEvent }) {
  const cfg = eventConfig[event.type] ?? eventConfig.ENTRY;
  const Icon = cfg.icon;
  const confColor = event.confidence >= 0.85 ? 'text-green-400' : event.confidence >= 0.65 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/5 transition-colors cursor-default">
      <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0', 'bg-white/5')}>
        <Icon size={14} className={cfg.color} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white">{event.visitor_id}</span>
          <span className="text-xs text-gray-500">{cfg.label}</span>
          <span className="text-xs text-gray-300 truncate">{event.zone}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={cn('text-xs font-medium', confColor)}>{(event.confidence * 100).toFixed(0)}%</span>
        <span className="text-xs text-gray-600">{event.time}</span>
      </div>
    </div>
  );
}

export function LiveTicker({ events }: LiveTickerProps) {
  const doubled = [...events, ...events]; // double for seamless loop

  return (
    <div className="relative">
      {/* Live indicator */}
      <div className="flex items-center gap-2 mb-3">
        <div className="pulse-dot">
          <div className="w-2 h-2 rounded-full bg-green-400" />
        </div>
        <span className="text-xs font-semibold text-green-400 uppercase tracking-wider">Live Feed</span>
        <span className="text-xs text-gray-500 ml-auto">{events.length} recent events</span>
      </div>

      {/* Scrolling ticker */}
      <div className="ticker-container h-64 overflow-hidden relative">
        {/* Fade overlays */}
        <div className="absolute top-0 left-0 right-0 h-8 z-10 pointer-events-none"
          style={{ background: 'linear-gradient(to bottom, #111827, transparent)' }} />
        <div className="absolute bottom-0 left-0 right-0 h-8 z-10 pointer-events-none"
          style={{ background: 'linear-gradient(to top, #111827, transparent)' }} />

        <div className="ticker-content">
          {doubled.map((event, idx) => (
            <TickerRow key={`${event.id}-${idx}`} event={event} />
          ))}
        </div>
      </div>
    </div>
  );
}

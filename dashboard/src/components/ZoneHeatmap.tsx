import { formatDuration } from '../lib/utils';

interface Zone {
  zone_id: string;
  zone_name: string;
  visitor_count: number;
  avg_dwell_seconds: number;
  occupancy_pct: number;
  camera_id: string;
}

interface ZoneHeatmapProps {
  zones: Zone[];
}

function getHeatColor(pct: number): string {
  // 0 = cool blue, 1 = hot red
  if (pct < 0.2) return '#1e40af';
  if (pct < 0.4) return '#1d4ed8';
  if (pct < 0.55) return '#2563eb';
  if (pct < 0.65) return '#7c3aed';
  if (pct < 0.75) return '#db2777';
  if (pct < 0.85) return '#dc2626';
  return '#b91c1c';
}

function getTextColor(pct: number): string {
  return pct > 0.5 ? '#ffffff' : '#e2e8f0';
}

export function ZoneHeatmap({ zones }: ZoneHeatmapProps) {
  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">Zone Occupancy Heatmap</span>
        <div className="flex items-center gap-2">
          <div className="flex rounded overflow-hidden h-3 w-32">
            {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((v) => (
              <div key={v} className="flex-1 h-full" style={{ background: getHeatColor(v) }} />
            ))}
          </div>
          <span className="text-xs text-gray-500">Low → High</span>
        </div>
      </div>

      {/* Grid Layout */}
      <div className="grid grid-cols-8 gap-2">
        {/* Row 1: Entry + Floor A + Floor B */}
        {zones.slice(0, 3).map((zone) => {
          const colSpan = zone.zone_id === 'entry' ? 'col-span-2' : 'col-span-3';
          const heatColor = getHeatColor(zone.occupancy_pct);
          const textColor = getTextColor(zone.occupancy_pct);
          return (
            <div
              key={zone.zone_id}
              className={`${colSpan} rounded-xl p-4 transition-all duration-500 cursor-pointer hover:scale-[1.02]`}
              style={{ background: heatColor, color: textColor }}
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-xs font-semibold opacity-80 uppercase tracking-wide">{zone.camera_id}</div>
                  <div className="text-sm font-bold mt-0.5">{zone.zone_name}</div>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold">{zone.visitor_count}</div>
                  <div className="text-xs opacity-75">visitors</div>
                </div>
              </div>
              <div className="mt-3 space-y-1">
                <div className="flex justify-between text-xs opacity-80">
                  <span>Avg Dwell</span>
                  <span className="font-semibold">{formatDuration(zone.avg_dwell_seconds)}</span>
                </div>
                <div className="flex justify-between text-xs opacity-80">
                  <span>Occupancy</span>
                  <span className="font-semibold">{(zone.occupancy_pct * 100).toFixed(0)}%</span>
                </div>
              </div>
              {/* Occupancy bar */}
              <div className="mt-2 h-1 bg-white/20 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white/70 rounded-full transition-all duration-700"
                  style={{ width: `${zone.occupancy_pct * 100}%` }}
                />
              </div>
            </div>
          );
        })}

        {/* Row 2: Billing A + Billing B */}
        {zones.slice(3).map((zone) => {
          const colSpan = zone.zone_id === 'billing-a' ? 'col-span-5' : 'col-span-3';
          const heatColor = getHeatColor(zone.occupancy_pct);
          const textColor = getTextColor(zone.occupancy_pct);
          return (
            <div
              key={zone.zone_id}
              className={`${colSpan} rounded-xl p-4 transition-all duration-500 cursor-pointer hover:scale-[1.02]`}
              style={{ background: heatColor, color: textColor }}
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-xs font-semibold opacity-80 uppercase tracking-wide">{zone.camera_id}</div>
                  <div className="text-sm font-bold mt-0.5">{zone.zone_name}</div>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold">{zone.visitor_count}</div>
                  <div className="text-xs opacity-75">visitors</div>
                </div>
              </div>
              <div className="mt-3 space-y-1">
                <div className="flex justify-between text-xs opacity-80">
                  <span>Avg Dwell</span>
                  <span className="font-semibold">{formatDuration(zone.avg_dwell_seconds)}</span>
                </div>
                <div className="flex justify-between text-xs opacity-80">
                  <span>Occupancy</span>
                  <span className="font-semibold">{(zone.occupancy_pct * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="mt-2 h-1 bg-white/20 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white/70 rounded-full transition-all duration-700"
                  style={{ width: `${zone.occupancy_pct * 100}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Traffic flow arrows */}
      <div className="flex items-center justify-center gap-2 mt-2 text-xs text-gray-500">
        <span>Entry</span>
        <span className="text-indigo-400">→</span>
        <span>Floor A/B</span>
        <span className="text-indigo-400">→</span>
        <span>Billing A/B</span>
        <span className="text-green-400">→</span>
        <span>Exit</span>
      </div>
    </div>
  );
}

import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  TrendingUp,
  Map,
  AlertTriangle,
  Activity,
  GitBranch,
  Shield,
  Zap,
  ChevronRight,
} from 'lucide-react';
import { cn } from '../lib/utils';

const navItems = [
  { path: '/', label: 'Executive Overview', icon: LayoutDashboard },
  { path: '/visitors', label: 'Live Visitors', icon: Users },
  { path: '/funnel', label: 'Conversion Funnel', icon: TrendingUp },
  { path: '/heatmap', label: 'Store Heatmap', icon: Map },
  { path: '/anomalies', label: 'Anomaly Center', icon: AlertTriangle },
  { path: '/health', label: 'System Health', icon: Activity },
  { path: '/journeys', label: 'Journey Explorer', icon: GitBranch },
  { path: '/identity', label: 'Identity Monitor', icon: Shield },
];

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const location = useLocation();

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-background border-r border-border transition-all duration-300 flex-shrink-0',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className={cn('flex items-center gap-3 px-4 py-5 border-b border-border bg-[#0a0514]', collapsed && 'justify-center px-2')}>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-accent flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/10">
          <Zap size={16} className="text-white fill-white/20" />
        </div>
        {!collapsed && (
          <div>
            <div className="text-sm font-bold text-white tracking-wider"><span className="text-accent">Purplle</span> APEX</div>
            <div className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mt-0.5">Store Intelligence</div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {!collapsed && (
          <div className="text-xs font-semibold text-gray-600 uppercase tracking-wider px-3 mb-3">
            Analytics
          </div>
        )}
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
          return (
            <NavLink
              key={path}
              to={path}
              className={cn(
                'nav-item',
                isActive ? 'active' : 'text-gray-400',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={16} className="flex-shrink-0" />
              {!collapsed && (
                <>
                  <span className="flex-1 text-sm">{label}</span>
                  {isActive && <ChevronRight size={12} className="text-indigo-400" />}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Store info */}
      {!collapsed && (
        <div className="px-4 py-4 border-t border-border bg-[#0b0514]">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 pulse-dot" />
            <div>
              <div className="text-xs font-semibold text-white">Brigade Road</div>
              <div className="text-xs text-gray-500">Bangalore · Live</div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

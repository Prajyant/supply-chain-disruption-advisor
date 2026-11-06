import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  MessageSquare,
  Settings,
  BookOpen,
  Anchor,
  Activity,
  Zap,
  ChevronRight,
} from 'lucide-react';
import { useViewMode, type ViewMode } from '../context/ViewModeContext';

const VIEW_MODES: { id: ViewMode; label: string; color: string; active: string }[] = [
  { id: 'analyst',    label: 'Analyst',    color: 'text-slate-400', active: 'bg-primary-600 text-white' },
  { id: 'operations', label: 'Ops',        color: 'text-slate-400', active: 'bg-blue-600 text-white' },
  { id: 'cfo',        label: 'CFO',        color: 'text-slate-400', active: 'bg-amber-500 text-slate-900' },
];

const NAV_ITEMS = [
  { path: '/',                label: 'Dashboard',      icon: LayoutDashboard },
  { path: '/digital-twin',   label: 'Digital Twin',   icon: Network },
  { path: '/vessel-tracking', label: 'Vessel Tracking', icon: Anchor },
  { path: '/chat',            label: 'AI Advisor',     icon: MessageSquare },
  { path: '/playbooks',       label: 'Playbooks',      icon: BookOpen },
  { path: '/settings',        label: 'Settings',       icon: Settings },
];

export function Layout() {
  const location = useLocation();
  const { viewMode, setViewMode } = useViewMode();
  const isCfo = viewMode === 'cfo';

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className={`w-60 shrink-0 flex flex-col bg-slate-900 border-r transition-colors duration-300 ${
        isCfo ? 'border-amber-500/30' : 'border-slate-800'
      }`}>

        {/* Logo */}
        <div className={`px-5 py-5 border-b ${isCfo ? 'border-amber-500/20' : 'border-slate-800'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-colors duration-300 ${
              isCfo ? 'bg-amber-500' : 'bg-primary-600'
            }`}>
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-white leading-tight">Supply Chain</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest leading-tight">Disruption Advisor</p>
            </div>
          </div>
          {isCfo && (
            <div className="mt-3 flex items-center gap-1.5 px-1">
              <Zap className="w-3 h-3 text-amber-400" />
              <span className="text-[10px] font-bold text-amber-400 uppercase tracking-widest">Executive View</span>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
            const isActive = path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(path);
            const activeClass = isCfo
              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/25'
              : 'bg-primary-600/15 text-primary-300 border border-primary-500/25';
            return (
              <Link
                key={path}
                to={path}
                className={`group flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all duration-150 border ${
                  isActive
                    ? activeClass
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? '' : 'group-hover:text-slate-200'}`} />
                  <span className="font-medium">{label}</span>
                </div>
                {isActive && <ChevronRight className="w-3.5 h-3.5 opacity-60" />}
              </Link>
            );
          })}
        </nav>

        {/* View Mode Switcher */}
        <div className={`px-3 pb-5 pt-3 border-t ${isCfo ? 'border-amber-500/20' : 'border-slate-800'}`}>
          <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-2 px-1">View Mode</p>
          <div className="flex rounded-lg overflow-hidden border border-slate-700/80 bg-slate-950/60">
            {VIEW_MODES.map((mode) => {
              const isSelected = viewMode === mode.id;
              return (
                <button
                  key={mode.id}
                  onClick={() => setViewMode(mode.id)}
                  title={mode.label}
                  className={`flex-1 py-2 text-xs font-semibold transition-all duration-200 ${
                    isSelected ? mode.active : `${mode.color} hover:text-white hover:bg-slate-800`
                  }`}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>
          <p className="text-[10px] text-slate-600 mt-1.5 text-center">
            {viewMode === 'analyst'    && 'Technical risk analysis'}
            {viewMode === 'operations' && 'Operational control center'}
            {viewMode === 'cfo'        && 'Executive financial briefing'}
          </p>
        </div>
      </aside>

      {/* ── Page content ── */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

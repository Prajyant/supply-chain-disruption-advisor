import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  MessageSquare,
  Settings,
  Package,
  BookOpen,
  Briefcase,
} from 'lucide-react';
import { useViewMode, type ViewMode } from '../context/ViewModeContext';

const VIEW_MODES: { id: ViewMode; label: string; short: string }[] = [
  { id: 'analyst',    label: 'Analyst',    short: 'A' },
  { id: 'operations', label: 'Operations', short: 'O' },
  { id: 'cfo',        label: 'CFO',        short: 'C' },
];

export function Layout() {
  const location = useLocation();
  const { viewMode, setViewMode } = useViewMode();
  const isCfo = viewMode === 'cfo';

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/digital-twin', label: 'Digital Twin', icon: Network },
    { path: '/chat', label: 'Chat Advisor', icon: MessageSquare },
    { path: '/playbooks', label: 'Playbooks', icon: BookOpen },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  const sidebarBorder = isCfo
    ? 'border-r border-amber-500/40'
    : 'border-r border-slate-800';

  const logoAccent = isCfo
    ? 'bg-amber-500'
    : 'bg-primary-600';

  const activeNavClass = isCfo
    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
    : 'bg-primary-600 text-white';

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar */}
      <aside className={`w-64 bg-slate-900 ${sidebarBorder} flex flex-col transition-colors duration-300`}>
        {/* Logo */}
        <div className={`p-6 border-b ${isCfo ? 'border-amber-500/20' : 'border-slate-800'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 ${logoAccent} rounded-lg flex items-center justify-center transition-colors duration-300`}>
              <Package className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-white">Supply Chain</h1>
              <p className="text-xs text-slate-400">Disruption Advisor</p>
            </div>
          </div>
          {isCfo && (
            <div className="mt-3 flex items-center gap-1.5">
              <Briefcase className="w-3 h-3 text-amber-400" />
              <span className="text-xs font-semibold text-amber-400 uppercase tracking-widest">Executive View</span>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive ? activeNavClass : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* View Mode Switcher */}
        <div className={`p-4 border-t ${isCfo ? 'border-amber-500/20' : 'border-slate-800'}`}>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 px-1">View Mode</p>
          <div className="flex rounded-lg overflow-hidden border border-slate-700 bg-slate-950/50">
            {VIEW_MODES.map((mode) => {
              const isSelected = viewMode === mode.id;
              let selectedClass = '';
              if (isSelected) {
                if (mode.id === 'cfo')        selectedClass = 'bg-amber-500 text-slate-900 font-bold';
                else if (mode.id === 'operations') selectedClass = 'bg-blue-600 text-white font-bold';
                else                          selectedClass = 'bg-primary-600 text-white font-bold';
              }
              return (
                <button
                  key={mode.id}
                  id={`view-mode-${mode.id}`}
                  onClick={() => setViewMode(mode.id)}
                  title={mode.label}
                  className={`flex-1 py-2 text-xs transition-all duration-200 ${
                    isSelected ? selectedClass : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>
          <p className="text-xs text-slate-600 mt-2 text-center">
            {viewMode === 'analyst' && 'Full technical analysis'}
            {viewMode === 'operations' && 'Operational control center'}
            {viewMode === 'cfo' && 'Executive briefing'}
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

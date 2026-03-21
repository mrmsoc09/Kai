import {
  ActivitySquare,
  Blocks,
  Compass,
  FileText,
  Gauge,
  ListChecks,
  Network,
  ShieldCheck,
  Waypoints,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useAppStore } from '../store/appStore';
import { hasAnyRole } from '../utils/auth';
import type { UserRole } from '../types';

interface NavigationItem {
  label: string;
  path: string;
  icon: (props: { className?: string }) => ReactNode;
  roles?: UserRole[];
}

const navigationItems: NavigationItem[] = [
  { label: 'Dashboard', path: '/dashboard', icon: (props) => <Gauge {...props} /> },
  { label: 'Mission Control', path: '/mission-control', icon: (props) => <Compass {...props} /> },
  { label: 'Intelligence Center', path: '/intelligence-center', icon: (props) => <Network {...props} /> },
  { label: 'Opportunities', path: '/opportunities', icon: (props) => <Waypoints {...props} /> },
  { label: 'Reports', path: '/reports', icon: (props) => <FileText {...props} />, roles: ['operator', 'analyst', 'admin'] },
  { label: 'Artifacts', path: '/artifacts', icon: (props) => <Blocks {...props} /> },
  { label: 'Governance', path: '/governance', icon: (props) => <ShieldCheck {...props} />, roles: ['operator', 'analyst', 'admin'] },
  { label: 'Simulation', path: '/simulation', icon: (props) => <ListChecks {...props} />, roles: ['analyst', 'admin'] },
];

const titleByPath = navigationItems.reduce<Record<string, string>>((accumulator, item) => {
  accumulator[item.path] = item.label;
  return accumulator;
}, {});

export function AppLayout() {
  const location = useLocation();
  const { auth, logout } = useAuth();
  const webSocketState = useAppStore((state) => state.webSocketState);
  const pageTitle = titleByPath[location.pathname] ?? 'Kai Console';
  const role = auth.user?.role;

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="hidden w-72 border-r border-slate-800/80 bg-slate-900/70 lg:flex lg:flex-col">
        <div className="border-b border-slate-800/80 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-cyan-500/20 p-2 text-cyan-300">
              <ActivitySquare className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-wide text-cyan-200">Kai Platform</p>
              <p className="text-xs text-slate-400">Security Intelligence Control Surface</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-4 py-6">
          <ul className="space-y-1">
            {navigationItems
              .filter((item) => !item.roles || hasAnyRole(role, item.roles))
              .map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                      isActive
                        ? 'bg-cyan-500/15 text-cyan-100'
                        : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-100'
                    }`}
                  >
                    {item.icon({ className: 'h-4 w-4' })}
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="border-t border-slate-800/80 px-4 py-4">
          <p className="mb-3 text-xs text-slate-400">
            Role: <span className="text-slate-200">{auth.user?.role ?? 'unknown'}</span>
          </p>
          <button
            type="button"
            onClick={logout}
            className="w-full rounded-lg border border-slate-700 bg-slate-800/50 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-700/60"
          >
            Sign Out
          </button>
        </div>
      </aside>
      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-800/80 bg-slate-950/90 px-6 backdrop-blur">
          <h1 className="text-base font-semibold tracking-wide text-slate-100">{pageTitle}</h1>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">WS</span>
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] uppercase tracking-wider font-medium ${
              webSocketState === 'connected'
                ? 'bg-emerald-500/15 text-emerald-300'
                : webSocketState === 'connecting' || webSocketState === 'idle'
                ? 'bg-amber-500/15 text-amber-300'
                : 'bg-rose-500/15 text-rose-300'
            }`}>
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                webSocketState === 'connected'
                  ? 'bg-emerald-400'
                  : webSocketState === 'connecting' || webSocketState === 'idle'
                  ? 'bg-amber-400'
                  : 'bg-rose-400'
              }`} />
              {webSocketState}
            </span>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

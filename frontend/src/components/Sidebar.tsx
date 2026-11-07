import React from 'react';
import {
  LayoutDashboard,
  Landmark,
  RefreshCw,
  ArrowUpRight,
  Bell,
  FileSpreadsheet,
  Building,
  Settings,
  ShieldCheck
} from 'lucide-react';
import { UserInfo } from '../types';

export type NavView =
  | 'dashboard'
  | 'instruments'
  | 'renewals'
  | 'releases'
  | 'notifications'
  | 'reports'
  | 'institutions'
  | 'administration';

interface SidebarProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  currentUser: UserInfo;
}

interface NavItemConfig {
  id: NavView;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor?: string;
  badge?: string | number;
}

const PRIMARY_NAV_ITEMS: NavItemConfig[] = [
  { id: 'dashboard', label: 'Dashboard Overview', icon: LayoutDashboard },
  { id: 'instruments', label: 'Security Deposits & FDRs', icon: Landmark, iconColor: 'text-blue-400' },
  { id: 'renewals', label: 'Renewals & Replacements', icon: RefreshCw, iconColor: 'text-amber-400' },
  { id: 'releases', label: 'Release & Refund Requests', icon: ArrowUpRight, iconColor: 'text-emerald-400' },
  { id: 'notifications', label: 'Maturity Alerts & Overdue', icon: Bell, iconColor: 'text-rose-400' },
  { id: 'reports', label: 'Reports & CSV Export', icon: FileSpreadsheet, iconColor: 'text-purple-400' },
  { id: 'institutions', label: 'Institutions Directory', icon: Building, iconColor: 'text-sky-400' },
];

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onNavigate,
  currentUser,
}) => {
  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col justify-between shrink-0 shadow-xl border-r border-slate-800">
      <div>
        {/* Brand Header */}
        <div className="px-4 py-4 border-b border-slate-800/80 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-700 to-indigo-950 border border-amber-500/30 flex items-center justify-center shadow-md shrink-0 p-1">
            <img src="/favicon.svg" alt="AICTE NIDHI" className="w-full h-full object-contain" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-black text-sm tracking-tight text-white flex items-center">
              <span className="truncate">AICTE NIDHI</span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium leading-tight">
              Security Deposit and FDR Management Portal
            </p>
          </div>
        </div>

        {/* Primary Navigation Menu */}
        <div className="px-3 py-4 space-y-1">
          <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Financial Instruments
          </div>

          {PRIMARY_NAV_ITEMS.map((item) => {
            const isSelected = currentView === item.id;
            const IconComponent = item.icon;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold leading-5 text-left transition-colors min-h-[40px] cursor-pointer ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <IconComponent
                  className={`w-4 h-4 shrink-0 self-start mt-0.5 ${item.iconColor || ''}`}
                />
                <span className="flex-1 min-w-0">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Area: Secondary Administration & Active Officer Session */}
      <div className="p-3 border-t border-slate-800/80 space-y-2">
        {/* Secondary Administration Section */}
        <button
          type="button"
          onClick={() => onNavigate('administration')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold leading-5 text-left transition-colors min-h-[38px] cursor-pointer ${
            currentView === 'administration'
              ? 'bg-slate-800 text-amber-300 border border-slate-700 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Settings className="w-4 h-4 shrink-0 self-start mt-0.5 text-slate-400" />
          <span className="flex-1 min-w-0">System Settings & Auth</span>
        </button>

        {/* User Session Info Card */}
        <div className="px-3 py-2 bg-slate-800/60 rounded-lg border border-slate-800 flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-[11px] font-bold text-white shrink-0">
            {currentUser.username[0].toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-slate-200 truncate">
              {currentUser.full_name || 'Regulation Officer'}
            </p>
            <p className="text-[10px] text-slate-400 truncate">
              {currentUser.designation || 'Regulation Bureau Officer'}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};

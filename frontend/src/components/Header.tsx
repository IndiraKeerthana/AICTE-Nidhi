import React from 'react';
import { Building2, AlertTriangle } from 'lucide-react';
import { UserInfo } from '../types';

interface HeaderProps {
  pageTitle: string;
  currentUser?: UserInfo;
  availableUsers?: UserInfo[];
  onSwitchUser?: (user: UserInfo) => void;
}

export const Header: React.FC<HeaderProps> = ({
  pageTitle,
  currentUser,
}) => {
  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shadow-xs shrink-0 relative z-20">
      <div className="flex items-center space-x-3">
        <h1 className="text-lg font-bold text-slate-800 tracking-tight">{pageTitle}</h1>
        <span className="hidden md:inline-flex items-center space-x-1.5 bg-slate-100 text-slate-700 text-[11px] font-medium px-2.5 py-0.5 rounded border border-slate-200">
          <Building2 className="w-3.5 h-3.5 text-blue-700" />
          <span>AICTE Regulation Bureau</span>
        </span>
        <span className="inline-flex items-center space-x-1 bg-amber-50 text-amber-800 border border-amber-300 text-[10px] font-bold px-2 py-0.5 rounded tracking-wide">
          <AlertTriangle className="w-3 h-3 text-amber-600" />
          <span>PROTOTYPE · SYNTHETIC DATA ONLY</span>
        </span>
      </div>

      <div className="flex items-center space-x-3">
        {/* Authorised Officer Session Badge */}
        <div className="flex items-center space-x-2 bg-blue-50 border border-blue-200/80 rounded-lg px-3 py-1.5 shadow-xs">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span className="text-xs font-bold text-blue-950">{currentUser?.role || 'OFFICER'}</span>
          <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-semibold border border-blue-200">
            AICTE NIDHI Session
          </span>
        </div>

        {/* Static Officer Profile */}
        <div className="flex items-center space-x-2 pl-2 border-l border-slate-200 select-none">
          <div className="w-8 h-8 rounded-full bg-blue-800 text-white flex items-center justify-center font-bold text-xs shadow-sm">
            R
          </div>
          <div className="hidden sm:block text-left">
            <p className="text-xs font-bold text-slate-800 leading-tight">
              Regulation Officer
            </p>
          </div>
        </div>
      </div>
    </header>
  );
};

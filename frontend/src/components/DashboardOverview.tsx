import React, { useState } from 'react';
import {
  Landmark,
  Clock,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ArrowUpRight,
  ShieldCheck,
  Search,
  ArrowRight,
  FileSpreadsheet,
  Building,
  Bell
} from 'lucide-react';
import { DashboardMetrics, UpcomingMaturityItem } from '../types';

interface DashboardOverviewProps {
  metrics: DashboardMetrics | null;
  loading?: boolean;
  onSelectInstrument: (id: number) => void;
  onNavigateToRegister: (filters?: { validity?: string; lifecycle?: string; bank?: string }) => void;
  onTriggerReminders: () => Promise<void>;
  onRefresh: () => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  metrics,
  loading = false,
  onSelectInstrument,
  onNavigateToRegister,
  onTriggerReminders,
  onRefresh,
}) => {
  const [remindersRunning, setRemindersRunning] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');

  const handleRunReminders = async () => {
    try {
      setRemindersRunning(true);
      await onTriggerReminders();
    } finally {
      setRemindersRunning(false);
    }
  };

  const filteredMaturities = (metrics?.upcoming_maturities || []).filter((item) => {
    if (!filterQuery) return true;
    const q = filterQuery.toLowerCase();
    return (
      item.instrument_number.toLowerCase().includes(q) ||
      item.institution_name.toLowerCase().includes(q) ||
      item.issuing_bank.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Banner & Quick Controls */}
      <div className="bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 rounded-xl p-6 text-white shadow-lg border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-blue-600/80 text-blue-100 text-[10px] font-bold px-2 py-0.5 rounded tracking-wider uppercase border border-blue-400/30">
              AICTE NIDHI
            </span>
            <span className="text-xs text-amber-300 font-semibold">Security Deposit and FDR Management Portal</span>
          </div>
          <h2 className="text-xl font-extrabold tracking-tight text-white">
            AICTE NIDHI — Security Deposit & FDR Command Center
          </h2>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
            Centralized monitoring of statutory institutional security deposits, bank lien endorsements, maturity schedules, and authorized release governance.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleRunReminders}
            disabled={remindersRunning}
            className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
          >
            <Bell className={`w-3.5 h-3.5 ${remindersRunning ? 'animate-bounce' : ''}`} />
            <span>{remindersRunning ? 'Scanning...' : 'Trigger Reminders'}</span>
          </button>

          <button
            type="button"
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors border border-slate-700 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {/* Total Portfolio */}
        <div
          onClick={() => onNavigateToRegister()}
          className="col-span-2 bg-white p-4 rounded-xl border border-slate-200 shadow-xs hover:border-blue-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Portfolio</span>
            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <Landmark className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-black text-slate-900 mt-2 tracking-tight">
            {metrics?.formatted_portfolio_amount || '₹0.00'}
          </p>
          <div className="flex items-center justify-between text-xs text-slate-500 mt-1">
            <span>{metrics?.total_instruments || 0} Instruments Enrolled</span>
            <span className="text-blue-600 font-semibold group-hover:underline flex items-center text-[11px]">
              View All <ArrowRight className="w-3 h-3 ml-0.5" />
            </span>
          </div>
        </div>

        {/* Active & Valid */}
        <div
          onClick={() => onNavigateToRegister({ validity: 'ACTIVE_VALID' })}
          className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs hover:border-emerald-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Active & Valid</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-black text-emerald-700 mt-2">
            {metrics?.active_valid || 0}
          </p>
          <p className="text-[10px] text-slate-500 mt-1">Lien Active & In-Date</p>
        </div>

        {/* Expiring Soon (<30d) */}
        <div
          onClick={() => onNavigateToRegister({ validity: 'EXPIRING_SOON' })}
          className="bg-white p-4 rounded-xl border border-amber-200 bg-amber-50/20 shadow-xs hover:border-amber-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800">Expiring &lt;30d</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-black text-amber-700 mt-2">
            {metrics?.expiring_soon_30d || 0}
          </p>
          <p className="text-[10px] text-amber-800 font-medium mt-1">Renewal Urgent</p>
        </div>

        {/* Matured */}
        <div
          onClick={() => onNavigateToRegister({ validity: 'MATURED' })}
          className="bg-white p-4 rounded-xl border border-rose-200 bg-rose-50/20 shadow-xs hover:border-rose-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-800">Matured</span>
            <AlertTriangle className="w-4 h-4 text-rose-600" />
          </div>
          <p className="text-2xl font-black text-rose-700 mt-2">
            {metrics?.matured || 0}
          </p>
          <p className="text-[10px] text-rose-800 font-medium mt-1">Overdue / Replaced</p>
        </div>

        {/* Pending Verification */}
        <div
          onClick={() => onNavigateToRegister({ lifecycle: 'PENDING_VERIFICATION' })}
          className="bg-white p-4 rounded-xl border border-purple-200 shadow-xs hover:border-purple-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-purple-800">Pending OCR/Verify</span>
            <AlertCircle className="w-4 h-4 text-purple-600" />
          </div>
          <p className="text-2xl font-black text-purple-700 mt-2">
            {metrics?.pending_verification || 0}
          </p>
          <p className="text-[10px] text-purple-800 font-medium mt-1">Checks In Progress</p>
        </div>

        {/* Release Requests */}
        <div
          onClick={() => onNavigateToRegister({ lifecycle: 'RELEASE_REQUESTED' })}
          className="bg-white p-4 rounded-xl border border-sky-200 shadow-xs hover:border-sky-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-sky-800">Release Requests</span>
            <ArrowUpRight className="w-4 h-4 text-sky-600" />
          </div>
          <p className="text-2xl font-black text-sky-700 mt-2">
            {metrics?.release_requests_pending || 0}
          </p>
          <p className="text-[10px] text-sky-800 font-medium mt-1">Clearance Pending</p>
        </div>
      </div>

      {/* Main Grid: Upcoming Maturities + Bank Portfolio */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upcoming Maturities Column (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-600" />
                <h3 className="text-sm font-bold text-slate-800">Upcoming Maturity Watchlist</h3>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Instruments expiring within regulatory notification window or past maturity
              </p>
            </div>

            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search FDR, Bank or College..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-full sm:w-60"
              />
            </div>
          </div>

          <div className="overflow-x-auto divide-y divide-slate-100 flex-1">
            {filteredMaturities.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No matching upcoming maturities found.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-4">Instrument / Institution</th>
                    <th className="py-2.5 px-4">Issuing Bank</th>
                    <th className="py-2.5 px-4">Amount</th>
                    <th className="py-2.5 px-4">Maturity Date</th>
                    <th className="py-2.5 px-4">Remaining</th>
                    <th className="py-2.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredMaturities.map((item) => {
                    const isMatured = item.days_remaining < 0;
                    const isExpiring = item.days_remaining >= 0 && item.days_remaining <= 30;

                    return (
                      <tr
                        key={item.id}
                        className="hover:bg-blue-50/40 transition-colors cursor-pointer group"
                        onClick={() => onSelectInstrument(item.id)}
                      >
                        <td className="py-3 px-4">
                          <p className="font-bold text-slate-900 group-hover:text-blue-700 flex items-center gap-1.5">
                            {item.instrument_number}
                          </p>
                          <p className="text-[11px] text-slate-500 truncate max-w-xs">
                            {item.institution_name}
                          </p>
                        </td>
                        <td className="py-3 px-4 text-slate-700 font-medium">
                          {item.issuing_bank}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900">
                          {item.formatted_amount}
                        </td>
                        <td className="py-3 px-4 text-slate-600">
                          {item.maturity_date}
                        </td>
                        <td className="py-3 px-4">
                          {isMatured ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">
                              {Math.abs(item.days_remaining)}d Overdue
                            </span>
                          ) : isExpiring ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 animate-pulse">
                              {item.days_remaining}d Left
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800">
                              {item.days_remaining}d Left
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectInstrument(item.id);
                            }}
                            className="px-2.5 py-1 text-[11px] font-bold text-blue-700 hover:text-white hover:bg-blue-700 rounded transition-colors border border-blue-200"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="p-3 bg-slate-50 border-t border-slate-200 text-center">
            <button
              type="button"
              onClick={() => onNavigateToRegister()}
              className="text-xs text-blue-700 hover:text-blue-800 font-semibold inline-flex items-center gap-1"
            >
              <span>View all security deposit instruments in register</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Right Column: Bank Distribution & Lifecycle Summary */}
        <div className="space-y-6">
          {/* Bank Allocation */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <Landmark className="w-4 h-4 text-blue-700" />
                <span>Issuing Bank Portfolio</span>
              </h3>
              <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-semibold">
                Scheduled Banks
              </span>
            </div>

            <div className="space-y-3">
              {(metrics?.bank_distribution || []).map((b) => {
                const totalAmt = metrics?.total_portfolio_amount || 1;
                const pct = Math.min(100, Math.round((b.total_amount / totalAmt) * 100));

                return (
                  <div
                    key={b.bank}
                    onClick={() => onNavigateToRegister({ bank: b.bank })}
                    className="p-2.5 rounded-lg border border-slate-100 hover:border-blue-300 hover:bg-blue-50/20 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-bold text-slate-800 group-hover:text-blue-700">{b.bank}</span>
                      <span className="text-slate-500 font-semibold">{b.count} FDRs ({pct}%)</span>
                    </div>
                    <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Regulatory Safeguards Notice */}
          <div className="bg-blue-50/60 rounded-xl border border-blue-200 p-4 text-xs text-blue-900 leading-relaxed space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-blue-950">
              <ShieldCheck className="w-4 h-4 text-blue-700 shrink-0" />
              <span>AICTE NIDHI · Regulatory Governance</span>
            </div>
            <p className="text-[11px] text-blue-800">
              Security deposits and Fixed Deposit Receipts (FDRs) remain held under joint lien with AICTE until formal completion of statutory commitments or authorized release.
            </p>
            <div className="pt-2 border-t border-blue-200/60 flex items-center justify-between text-[10px] text-blue-700 font-medium">
              <span>AICTE NIDHI Verification Active</span>
              <span className="font-bold text-blue-900">AICTE Reg. Manual 2024-2027</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState, useMemo } from 'react';
import {
  Landmark,
  Search,
  Filter,
  Download,
  Plus,
  Clock,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowUpDown,
  Building,
  RefreshCw,
  FileSpreadsheet
} from 'lucide-react';
import { DepositInstrument, LifecycleStatus, ValidityStatus, VerificationStatus } from '../types';
import { getExportCsvUrl } from '../services/api';

interface InstrumentRegisterProps {
  instruments: DepositInstrument[];
  loading?: boolean;
  initialFilters?: {
    validity?: string;
    lifecycle?: string;
    bank?: string;
  };
  onSelectInstrument: (id: number) => void;
  onRefresh: () => void;
  onCreateNew?: () => void;
}

export const InstrumentRegister: React.FC<InstrumentRegisterProps> = ({
  instruments,
  loading = false,
  initialFilters,
  onSelectInstrument,
  onRefresh,
  onCreateNew,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [bankFilter, setBankFilter] = useState(initialFilters?.bank || 'ALL');
  const [validityFilter, setValidityFilter] = useState(initialFilters?.validity || 'ALL');
  const [lifecycleFilter, setLifecycleFilter] = useState(initialFilters?.lifecycle || 'ALL');
  const [sortBy, setSortBy] = useState<'maturity_date' | 'amount' | 'submission_date'>('maturity_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Unique bank options
  const bankOptions = useMemo(() => {
    const set = new Set<string>();
    instruments.forEach((inst) => {
      if (inst.issuing_bank) set.add(inst.issuing_bank);
    });
    return Array.from(set).sort();
  }, [instruments]);

  // Filtered and sorted instruments
  const filteredInstruments = useMemo(() => {
    return instruments.filter((inst) => {
      if (bankFilter !== 'ALL' && inst.issuing_bank !== bankFilter) return false;
      if (validityFilter !== 'ALL' && inst.validity_status !== validityFilter) return false;
      if (lifecycleFilter !== 'ALL' && inst.lifecycle_status !== lifecycleFilter) return false;

      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        const matchFdr = inst.instrument_number.toLowerCase().includes(q);
        const matchBank = inst.issuing_bank?.toLowerCase().includes(q);
        const matchInst = inst.institution?.name?.toLowerCase().includes(q);
        const matchId = inst.institution?.aicte_permanent_id?.toLowerCase().includes(q);
        if (!matchFdr && !matchBank && !matchInst && !matchId) return false;
      }

      return true;
    }).sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'maturity_date') {
        comparison = (a.maturity_date || '').localeCompare(b.maturity_date || '');
      } else if (sortBy === 'amount') {
        comparison = (a.amount || 0) - (b.amount || 0);
      } else if (sortBy === 'submission_date') {
        comparison = (a.submission_date || '').localeCompare(b.submission_date || '');
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [instruments, bankFilter, validityFilter, lifecycleFilter, searchTerm, sortBy, sortOrder]);

  const handleExportCsv = () => {
    const url = getExportCsvUrl({
      bank: bankFilter !== 'ALL' ? bankFilter : undefined,
      validity_status: validityFilter !== 'ALL' ? validityFilter : undefined,
      lifecycle_status: lifecycleFilter !== 'ALL' ? lifecycleFilter : undefined,
      search: searchTerm.trim() || undefined,
    });
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-4">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Landmark className="w-5 h-5 text-blue-700" />
            <span>Security Deposit & Fixed Deposit Receipt Register</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Complete institutional instrument ledger ({filteredInstruments.length} of {instruments.length} instruments matching)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition-colors border border-slate-300 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          <button
            type="button"
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold text-xs rounded-lg transition-colors border border-blue-200 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search Box */}
          <div className="lg:col-span-2 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by FDR #, Bank, College name, or AICTE ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
            />
          </div>

          {/* Bank Filter */}
          <div>
            <select
              value={bankFilter}
              onChange={(e) => setBankFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="ALL">All Issuing Banks</option>
              {bankOptions.map((bank) => (
                <option key={bank} value={bank}>{bank}</option>
              ))}
            </select>
          </div>

          {/* Validity Status */}
          <div>
            <select
              value={validityFilter}
              onChange={(e) => setValidityFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="ALL">All Validity States</option>
              <option value="ACTIVE_VALID">Active & Valid</option>
              <option value="EXPIRING_SOON">Expiring Soon (&lt;30d)</option>
              <option value="MATURED">Matured / Overdue</option>
            </select>
          </div>

          {/* Lifecycle Status */}
          <div>
            <select
              value={lifecycleFilter}
              onChange={(e) => setLifecycleFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="ALL">All Lifecycle States</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="SUBMITTED">SUBMITTED</option>
              <option value="PENDING_VERIFICATION">PENDING_VERIFICATION</option>
              <option value="RENEWAL_REQUIRED">RENEWAL_REQUIRED</option>
              <option value="RELEASE_REQUESTED">RELEASE_REQUESTED</option>
              <option value="RELEASED">RELEASED</option>
              <option value="SUPERSEDED">SUPERSEDED</option>
            </select>
          </div>
        </div>

        {/* Sort and active filter chips */}
        <div className="flex flex-wrap items-center justify-between text-xs pt-1 border-t border-slate-100 text-slate-500">
          <div className="flex items-center gap-2">
            <span>Sort by:</span>
            <button
              type="button"
              onClick={() => {
                if (sortBy === 'maturity_date') setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                else { setSortBy('maturity_date'); setSortOrder('asc'); }
              }}
              className={`px-2 py-1 rounded text-xs font-medium cursor-pointer ${
                sortBy === 'maturity_date' ? 'bg-blue-100 text-blue-800 font-bold' : 'hover:bg-slate-100'
              }`}
            >
              Maturity Date {sortBy === 'maturity_date' && (sortOrder === 'asc' ? '↑' : '↓')}
            </button>
            <button
              type="button"
              onClick={() => {
                if (sortBy === 'amount') setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                else { setSortBy('amount'); setSortOrder('desc'); }
              }}
              className={`px-2 py-1 rounded text-xs font-medium cursor-pointer ${
                sortBy === 'amount' ? 'bg-blue-100 text-blue-800 font-bold' : 'hover:bg-slate-100'
              }`}
            >
              Amount {sortBy === 'amount' && (sortOrder === 'asc' ? '↑' : '↓')}
            </button>
          </div>

          {(bankFilter !== 'ALL' || validityFilter !== 'ALL' || lifecycleFilter !== 'ALL' || searchTerm) && (
            <button
              type="button"
              onClick={() => {
                setBankFilter('ALL');
                setValidityFilter('ALL');
                setLifecycleFilter('ALL');
                setSearchTerm('');
              }}
              className="text-blue-600 hover:underline font-semibold cursor-pointer"
            >
              Reset all filters
            </button>
          )}
        </div>
      </div>

      {/* Instruments Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Instrument Details</th>
                <th className="py-3 px-4">Institution & AICTE ID</th>
                <th className="py-3 px-4">Issuing Bank & Branch</th>
                <th className="py-3 px-4">Amount (INR)</th>
                <th className="py-3 px-4">Maturity Date</th>
                <th className="py-3 px-4">Validity</th>
                <th className="py-3 px-4">Verification</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredInstruments.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No deposit instruments found matching the specified criteria.
                  </td>
                </tr>
              ) : (
                filteredInstruments.map((inst) => {
                  const days = inst.days_to_maturity ?? 0;
                  const isMatured = inst.validity_status === 'MATURED';
                  const isExpiring = inst.validity_status === 'EXPIRING_SOON';

                  return (
                    <tr
                      key={inst.id}
                      onClick={() => onSelectInstrument(inst.id)}
                      className="hover:bg-blue-50/40 transition-colors cursor-pointer group"
                    >
                      {/* Instrument Number & Type */}
                      <td className="py-3 px-4">
                        <p className="font-bold text-slate-900 group-hover:text-blue-700 font-mono">
                          {inst.instrument_number}
                        </p>
                        <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-semibold">
                          {inst.instrument_type}
                        </span>
                        {inst.renewal_count > 0 && (
                          <span className="ml-1 text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.2 rounded font-semibold">
                            R{inst.renewal_count}
                          </span>
                        )}
                      </td>

                      {/* Institution */}
                      <td className="py-3 px-4 max-w-xs">
                        <p className="font-semibold text-slate-800 truncate">
                          {inst.institution?.name || `Institution #${inst.institution_id}`}
                        </p>
                        <p className="text-[10px] text-slate-400 font-mono">
                          {inst.institution?.aicte_permanent_id || 'ID Pending'}
                        </p>
                      </td>

                      {/* Issuing Bank */}
                      <td className="py-3 px-4">
                        <p className="font-semibold text-slate-800">{inst.issuing_bank}</p>
                        <p className="text-[10px] text-slate-500 truncate">{inst.branch_name || 'Main Branch'}</p>
                      </td>

                      {/* Amount */}
                      <td className="py-3 px-4">
                        <p className="font-bold text-slate-900">
                          {inst.formatted_amount || `₹${inst.amount.toLocaleString('en-IN')}`}
                        </p>
                      </td>

                      {/* Maturity Date */}
                      <td className="py-3 px-4">
                        <p className="text-slate-800 font-medium">{inst.maturity_date}</p>
                        <p className="text-[10px] text-slate-400">Issue: {inst.issue_date}</p>
                      </td>

                      {/* Dynamic Validity */}
                      <td className="py-3 px-4">
                        {isMatured ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">
                            Matured ({Math.abs(days)}d ago)
                          </span>
                        ) : isExpiring ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 animate-pulse">
                            Expiring ({days}d left)
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800">
                            Active ({days}d)
                          </span>
                        )}
                      </td>

                      {/* Verification Status */}
                      <td className="py-3 px-4">
                        {inst.verification_status === 'VERIFIED' ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Verified</span>
                          </span>
                        ) : inst.verification_status === 'DISCREPANCY_FLAGGED' ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                            <span>Discrepancy</span>
                          </span>
                        ) : inst.verification_status === 'VERIFICATION_FAILED' ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-700">
                            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                            <span>Failed</span>
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400">Unverified</span>
                        )}
                      </td>

                      {/* Lifecycle Status */}
                      <td className="py-3 px-4">
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wide ${
                          inst.lifecycle_status === 'ACTIVE'
                            ? 'bg-blue-100 text-blue-800 border border-blue-200'
                            : inst.lifecycle_status === 'RENEWAL_REQUIRED'
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : inst.lifecycle_status === 'RELEASE_REQUESTED'
                            ? 'bg-purple-100 text-purple-800 border border-purple-200'
                            : inst.lifecycle_status === 'RELEASED'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : inst.lifecycle_status === 'SUPERSEDED'
                            ? 'bg-slate-100 text-slate-600 border border-slate-300'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}>
                          {inst.lifecycle_status}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectInstrument(inst.id);
                          }}
                          className="px-2.5 py-1 text-xs font-bold text-blue-700 hover:text-white hover:bg-blue-700 rounded transition-colors border border-blue-200 cursor-pointer"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


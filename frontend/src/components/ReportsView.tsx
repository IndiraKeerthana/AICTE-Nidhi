import React, { useState, useEffect } from 'react';
import {
  FileSpreadsheet,
  Download,
  Landmark,
  ShieldCheck,
  RefreshCw,
  PieChart,
  BarChart2
} from 'lucide-react';
import { fetchReportsSummary, getExportCsvUrl } from '../services/api';

export const ReportsView: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadSummary = async () => {
    try {
      setLoading(true);
      const data = await fetchReportsSummary();
      setSummary(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  const handleDownloadFullExport = () => {
    window.open(getExportCsvUrl(), '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-purple-600" />
            <span>AICTE NIDHI Deposit & Corpus Reports & Data Exports</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit-grade portfolio summaries, scheduled commercial bank breakdowns, and RFC 4180 compliant CSV exports.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleDownloadFullExport}
            className="flex items-center gap-1.5 px-3 py-2 bg-purple-700 hover:bg-purple-800 text-white font-bold text-xs rounded-lg transition-colors shadow-xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Full CSV Export</span>
          </button>

          <button
            type="button"
            onClick={loadSummary}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition-colors border border-slate-300 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Total Enrolled Instruments
          </span>
          <p className="text-3xl font-black text-slate-900 mt-2">
            {summary?.total_instruments || 0}
          </p>
          <p className="text-xs text-slate-500 mt-1">Across all participating institutions</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Aggregate Security Corpus
          </span>
          <p className="text-3xl font-black text-blue-700 mt-2">
            {summary?.formatted_total_amount || '₹0.00'}
          </p>
          <p className="text-xs text-slate-500 mt-1">Total statutory value held under joint lien</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Export Format & Compliance
          </span>
          <p className="text-base font-bold text-slate-800 mt-2">
            RFC 4180 CSV & UTF-8
          </p>
          <p className="text-xs text-slate-500 mt-1">Includes formula injection sanitization</p>
        </div>
      </div>

      {/* Bank Allocation Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <Landmark className="w-4 h-4 text-blue-700" />
            <span>Issuing Scheduled Bank Portfolio Allocation</span>
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-4">Issuing Bank Name</th>
                <th className="py-2.5 px-4 text-center">FDR Count</th>
                <th className="py-2.5 px-4 text-right">Aggregate Corpus (INR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(!summary?.bank_distribution || summary.bank_distribution.length === 0) ? (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-slate-400">
                    No bank distribution data available.
                  </td>
                </tr>
              ) : (
                summary.bank_distribution.map((b: any) => (
                  <tr key={b.bank} className="hover:bg-slate-50/60">
                    <td className="py-3 px-4 font-bold text-slate-800">{b.bank}</td>
                    <td className="py-3 px-4 text-center font-semibold text-slate-700">{b.count}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                      ₹{Number(b.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


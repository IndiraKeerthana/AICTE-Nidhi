import React, { useState, useEffect } from 'react';
import {
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Building,
  Landmark,
  FileText
} from 'lucide-react';
import { RenewalRecord, DepositInstrument } from '../types';
import {
  fetchRenewals,
  recordRenewalDecision,
  registerReplacement
} from '../services/api';

interface RenewalsViewProps {
  onSelectInstrument: (id: number) => void;
}

export const RenewalsView: React.FC<RenewalsViewProps> = ({ onSelectInstrument }) => {
  const [renewals, setRenewals] = useState<RenewalRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRenewal, setSelectedRenewal] = useState<RenewalRecord | null>(null);

  // Decision Modal
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [decisionType, setDecisionType] = useState<'APPROVED' | 'REJECTED' | 'RECTIFICATION_REQUESTED'>('APPROVED');
  const [decisionRemarks, setDecisionRemarks] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showReplacementModal, setShowReplacementModal] = useState(false);
  const [replacementTarget, setReplacementTarget] = useState<RenewalRecord | null>(null);
  const [replacementNumber, setReplacementNumber] = useState('');
  const [replacementBank, setReplacementBank] = useState('');
  const [replacementAmount, setReplacementAmount] = useState('');
  const [replacementMaturity, setReplacementMaturity] = useState('');
  const [replacementBranch, setReplacementBranch] = useState('');

  const loadRenewals = async () => {
    try {
      setLoading(true);
      const data = await fetchRenewals();
      setRenewals(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRenewals();
  }, []);

  const handleReplacementSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replacementTarget) return;
    try {
      setSubmitting(true);
      await registerReplacement(replacementTarget.id, {
        replacement_instrument_number: replacementNumber,
        issuing_bank: replacementBank,
        amount: Number(replacementAmount),
        new_maturity_date: replacementMaturity,
        branch_name: replacementBranch || undefined,
      });
      setShowReplacementModal(false);
      setReplacementTarget(null);
      setReplacementNumber('');
      setReplacementBank('');
      setReplacementAmount('');
      setReplacementMaturity('');
      setReplacementBranch('');
      await loadRenewals();
    } catch (err: any) {
      alert(`Replacement registration failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecisionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRenewal) return;

    try {
      setSubmitting(true);
      await recordRenewalDecision(selectedRenewal.id, {
        decision: decisionType,
        remarks: decisionRemarks,
      });
      setShowDecisionModal(false);
      setSelectedRenewal(null);
      loadRenewals();
    } catch (err: any) {
      alert(`Decision failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-amber-600" />
            <span>Deposit Renewals & Replacement Instruments Queue</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage statutory tenure extensions, replacement FDR receipt linking, and authorized approval workflows.
          </p>
        </div>

        <button
          type="button"
          onClick={loadRenewals}
          className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition-colors border border-slate-300 cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Renewals Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Renewal ID</th>
                <th className="py-3 px-4">Original FDR</th>
                <th className="py-3 px-4">Replacement FDR</th>
                <th className="py-3 px-4">Previous Maturity</th>
                <th className="py-3 px-4">New Maturity Date</th>
                <th className="py-3 px-4">Review Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {renewals.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No active renewal or replacement records in the queue.
                  </td>
                </tr>
              ) : (
                renewals.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      #REN-{r.id.toString().padStart(4, '0')}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        type="button"
                        onClick={() => onSelectInstrument(r.original_instrument_id)}
                        className="font-bold text-blue-700 hover:underline font-mono cursor-pointer"
                      >
                        {r.original_instrument?.instrument_number || `Instrument #${r.original_instrument_id}`}
                      </button>
                      <p className="text-[10px] text-slate-500">{r.original_instrument?.issuing_bank}</p>
                    </td>
                    <td className="py-3 px-4">
                      {r.replacement_instrument_id ? (
                        <div>
                          <button
                            type="button"
                            onClick={() => onSelectInstrument(r.replacement_instrument_id!)}
                            className="font-bold text-emerald-700 hover:underline font-mono cursor-pointer"
                          >
                            {r.replacement_instrument?.instrument_number || `Replacement #${r.replacement_instrument_id}`}
                          </button>
                          <span className="ml-1 text-[9px] bg-emerald-100 text-emerald-800 px-1 rounded">Linked</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Pending Registration</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {r.previous_maturity_date}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      {r.new_maturity_date}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                        r.review_status === 'APPROVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : r.review_status === 'REJECTED'
                          ? 'bg-rose-100 text-rose-800'
                          : r.review_status === 'RECTIFICATION_REQUESTED'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        {r.review_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {!r.replacement_instrument_id && r.review_status !== 'REJECTED' && (
                        <button
                          type="button"
                          onClick={() => {
                            setReplacementTarget(r);
                            setReplacementMaturity(r.new_maturity_date || '');
                            setShowReplacementModal(true);
                          }}
                          className="mr-2 px-2.5 py-1 text-xs font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded cursor-pointer"
                        >
                          Register Replacement
                        </button>
                      )}
                      {r.review_status !== 'APPROVED' && r.review_status !== 'REJECTED' ? (
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedRenewal(r);
                            setShowDecisionModal(true);
                          }}
                          className="px-2.5 py-1 text-xs font-bold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded cursor-pointer"
                        >
                          Decide
                        </button>
                      ) : (
                        <span className="text-[11px] text-slate-400 font-medium">Decided</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Replacement Instrument Modal */}
      {showReplacementModal && replacementTarget && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-base font-bold text-slate-900">Register Replacement FDR</h3>
            <p className="text-xs text-slate-500 mt-1">Link the new instrument to renewal #{replacementTarget.id}.</p>
            <form onSubmit={handleReplacementSubmit} className="mt-4 space-y-3">
              <input required value={replacementNumber} onChange={e => setReplacementNumber(e.target.value)} placeholder="Replacement FDR number" className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg" />
              <input required value={replacementBank} onChange={e => setReplacementBank(e.target.value)} placeholder="Issuing bank" className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg" />
              <input required type="number" min="1" step="0.01" value={replacementAmount} onChange={e => setReplacementAmount(e.target.value)} placeholder="Amount (INR)" className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg" />
              <input required type="date" value={replacementMaturity} onChange={e => setReplacementMaturity(e.target.value)} className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg" />
              <input value={replacementBranch} onChange={e => setReplacementBranch(e.target.value)} placeholder="Branch (optional)" className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg" />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowReplacementModal(false)} className="px-3 py-2 text-xs text-slate-600 rounded-lg hover:bg-slate-100">Cancel</button>
                <button type="submit" disabled={submitting} className="px-4 py-2 text-xs bg-emerald-700 text-white font-bold rounded-lg disabled:opacity-50">{submitting ? 'Registering...' : 'Register Replacement'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Decision Modal */}
      {showDecisionModal && selectedRenewal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-base font-bold text-slate-900">Record Renewal Decision</h3>
            <p className="text-xs text-slate-500 mt-1">
              Renewal Record #{selectedRenewal.id} for {selectedRenewal.original_instrument?.instrument_number}
            </p>

            <form onSubmit={handleDecisionSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Official Decision *
                </label>
                <select
                  value={decisionType}
                  onChange={(e) => setDecisionType(e.target.value as any)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                >
                  <option value="APPROVED">APPROVE (Accept Tenure Extension & Mark Active)</option>
                  <option value="RECTIFICATION_REQUESTED">RECTIFICATION_REQUESTED (Return to Institution)</option>
                  <option value="REJECTED">REJECT (Decline Renewal Submission)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Review Observations / Regulatory Reason *
                </label>
                <textarea
                  required
                  rows={3}
                  value={decisionRemarks}
                  onChange={(e) => setDecisionRemarks(e.target.value)}
                  placeholder="Official observations regarding the replacement FDR receipt and bank lien letter..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                ></textarea>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDecisionModal(false)}
                  className="px-3 py-2 text-xs text-slate-600 font-semibold hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-xs bg-blue-700 hover:bg-blue-800 text-white font-bold rounded-lg cursor-pointer"
                >
                  {submitting ? 'Recording...' : 'Submit Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};


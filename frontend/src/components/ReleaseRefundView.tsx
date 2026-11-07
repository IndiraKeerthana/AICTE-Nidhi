import React, { useState, useEffect } from 'react';
import {
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileText,
  Building,
  RefreshCw,
  Clock,
  Landmark
} from 'lucide-react';
import { ReleaseRefundRequest, ChecklistItem, UserInfo } from '../types';
import {
  fetchReleases,
  recordReleaseDecision
} from '../services/api';

interface ReleaseRefundViewProps {
  currentUser: UserInfo;
  onSelectInstrument: (id: number) => void;
}

export const ReleaseRefundView: React.FC<ReleaseRefundViewProps> = ({
  currentUser,
  onSelectInstrument,
}) => {
  const [requests, setRequests] = useState<ReleaseRefundRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<ReleaseRefundRequest | null>(null);

  // Review & Decision Form
  const [showModal, setShowModal] = useState(false);
  const [decision, setDecision] = useState<'RECOMMEND' | 'APPROVE' | 'REJECT' | 'RETURN_FOR_CORRECTION'>('RECOMMEND');
  const [remarks, setRemarks] = useState('');
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const loadReleases = async () => {
    try {
      setLoading(true);
      const data = await fetchReleases();
      setRequests(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReleases();
  }, []);

  const handleOpenReview = (req: ReleaseRefundRequest) => {
    setSelectedRequest(req);
    // Initialize checklist items
    let savedChecklist: ChecklistItem[] = [];
    try {
      const parsed = req.conditions_checklist_json ? JSON.parse(req.conditions_checklist_json as any) : {};
      savedChecklist = Object.entries(parsed).map(([condition_key, value]: [string, any]) => ({
        condition_key,
        label: value.label || condition_key,
        satisfied: Boolean(value.verified),
      }));
    } catch {
      savedChecklist = [];
    }
    setChecklist(savedChecklist.length ? savedChecklist : [
      { condition_key: 'continuous_operation_years_satisfied', label: 'Prescribed institutional operational period completed', satisfied: false },
      { condition_key: 'no_pending_student_grievances', label: 'No unresolved student grievances or litigation', satisfied: false },
      { condition_key: 'audited_financial_accounts_clean', label: 'Audited financial accounts and compliance records are up to date', satisfied: false },
      { condition_key: 'competent_authority_in_principle_approval', label: 'Competent authority in-principle approval obtained', satisfied: false },
      { condition_key: 'original_fdr_discharge_undertaking', label: 'Original FDR discharge undertaking submitted', satisfied: false },
    ]);

    const isApprover = currentUser.role === 'APPROVER' || currentUser.role === 'ADMIN';
    setDecision(isApprover ? 'APPROVE' : 'RETURN_FOR_CORRECTION');
    setRemarks('');
    setShowModal(true);
  };

  const handleChecklistToggle = (index: number) => {
    setChecklist((prev) =>
      prev.map((item, idx) =>
        idx === index ? { ...item, satisfied: !item.satisfied } : item
      )
    );
  };

  const handleSubmitDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRequest) return;

    try {
      setSubmitting(true);
      await recordReleaseDecision(selectedRequest.id, {
        decision,
        remarks,
        conditions_checklist: Object.fromEntries(checklist.map((item) => [item.condition_key, item.satisfied])),
      });
      setShowModal(false);
      setSelectedRequest(null);
      loadReleases();
    } catch (err: any) {
      alert(`Decision recording failed: ${err.message}`);
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
            <ArrowUpRight className="w-5 h-5 text-emerald-600" />
            <span>Deposit Release & Refund Governance Queue</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluate statutory release prerequisites, verify trust payee bank accounts, and record the competent authority's demo decision.
          </p>
        </div>

        <button
          type="button"
          onClick={loadReleases}
          className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition-colors border border-slate-300 cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Requests Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Request #</th>
                <th className="py-3 px-4">FDR Instrument</th>
                <th className="py-3 px-4">Institution Name</th>
                <th className="py-3 px-4">Release Type</th>
                <th className="py-3 px-4">Beneficiary Account</th>
                <th className="py-3 px-4">Approval Stage</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {requests.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No release or refund requests currently pending.
                  </td>
                </tr>
              ) : (
                requests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      {req.request_number}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        type="button"
                        onClick={() => onSelectInstrument(req.instrument_id)}
                        className="font-bold text-blue-700 hover:underline font-mono cursor-pointer"
                      >
                        {req.instrument_number || `FDR #${req.instrument_id}`}
                      </button>
                      <p className="text-[10px] text-slate-500 font-bold">
                        
                      </p>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-semibold text-slate-800 truncate max-w-xs">
                        {req.institution_name}
                      </p>
                      <p className="text-[10px] text-slate-400 font-mono">
                        
                      </p>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">
                        {req.request_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-mono text-slate-800">N/A</p>
                      <p className="text-[10px] text-slate-400 font-mono"></p>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                        req.review_status === 'COMPLETED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : req.review_status === 'REJECTED'
                          ? 'bg-rose-100 text-rose-800'
                          : req.review_status === 'SUBMITTED'
                          ? 'bg-purple-100 text-purple-800'
                          : req.review_status === 'RETURNED_FOR_CORRECTION'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        {req.review_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleOpenReview(req)}
                        className="px-2.5 py-1 text-xs font-bold text-blue-800 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded cursor-pointer"
                      >
                        Review Checklist
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Checklist & Approval Decision Modal */}
      {showModal && selectedRequest && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 border border-slate-200 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Release Clearance Review
                </span>
                <h3 className="text-base font-bold text-slate-900">
                  {selectedRequest.request_number}
                </h3>
              </div>
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                {selectedRequest.review_status}
              </span>
            </div>

            <div className="mt-3 text-xs text-slate-600 bg-slate-50 p-3 rounded-lg space-y-1">
              <p><span className="font-bold">Instrument:</span> {selectedRequest.instrument_number || `FDR #${selectedRequest.instrument_id}`}</p>
              <p><span className="font-bold">Institution:</span> {selectedRequest.institution_name}</p>
              <p><span className="font-bold">Remittance:</span> Details are included in the submitted request reason.</p>
            </div>

            <form onSubmit={handleSubmitDecision} className="mt-4 space-y-4">
              {/* 5-Point Conditions Checklist */}
              <div>
                <label className="block text-xs font-bold text-slate-800 mb-2">
                  Statutory Release Conditions Checklist
                </label>
                <div className="space-y-2 border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                  {checklist.map((item, idx) => (
                    <label key={item.condition_key} className="flex items-start gap-2.5 cursor-pointer text-xs">
                      <input
                        type="checkbox"
                        checked={item.satisfied}
                        onChange={() => handleChecklistToggle(idx)}
                        className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className={`text-slate-800 ${item.satisfied ? 'font-medium' : 'text-slate-500'}`}>
                        {item.label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Decision Selection */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">Authority Decision</label>
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as any)}
                  className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg font-bold"
                >
                  <option value="APPROVE">APPROVE RELEASE</option>
                  <option value="RETURN_FOR_CORRECTION">RETURN FOR CORRECTION</option>
                  <option value="REJECT">REJECT REQUEST</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Official Remarks & Findings *
                </label>
                <textarea
                  required
                  rows={3}
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Record formal compliance findings and authorization reference..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                ></textarea>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-2 text-xs text-slate-600 font-semibold hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-xs bg-emerald-700 hover:bg-emerald-800 text-white font-bold rounded-lg cursor-pointer"
                >
                  {submitting ? 'Recording...' : 'Record Authorized Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};


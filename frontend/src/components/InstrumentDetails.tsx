import React, { useState } from 'react';
import {
  ArrowLeft,
  Landmark,
  Calendar,
  Building,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileText,
  Upload,
  RefreshCw,
  ExternalLink,
  Clock,
  ArrowUpRight,
  Eye,
  Hash,
  Check,
  FileCheck
} from 'lucide-react';
import {
  InstrumentDetail,
  InstrumentDocument,
  VerificationRecord,
  LifecycleStatus,
  ValidityStatus
} from '../types';
import {
  triggerInstrumentVerification,
  uploadInstrumentDocument,
  initiateRenewal,
  submitReleaseRequest,
  updateInstrumentLifecycle
} from '../services/api';
import { DocumentViewerModal } from './DocumentViewerModal';

interface InstrumentDetailsProps {
  instrument: InstrumentDetail;
  onBack: () => void;
  onRefresh: () => void;
}

export const InstrumentDetails: React.FC<InstrumentDetailsProps> = ({
  instrument,
  onBack,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'documents' | 'discrepancies' | 'verification' | 'audit'>('overview');
  const [verifying, setVerifying] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedDocForViewer, setSelectedDocForViewer] = useState<InstrumentDocument | null>(null);

  // Renewal Modal State
  const [showRenewalModal, setShowRenewalModal] = useState(false);
  const [newMaturityDate, setNewMaturityDate] = useState('');
  const [renewalNotes, setRenewalNotes] = useState('');
  const [renewalSubmitting, setRenewalSubmitting] = useState(false);

  // Release Request Modal State
  const [showReleaseModal, setShowReleaseModal] = useState(false);
  const [releaseBankAccount, setReleaseBankAccount] = useState('');
  const [releaseBankIfsc, setReleaseBankIfsc] = useState('');
  const [releaseBeneficiary, setReleaseBeneficiary] = useState('');
  const [releaseSubmitting, setReleaseSubmitting] = useState(false);

  const days = instrument.days_to_maturity ?? 0;
  const isMatured = instrument.validity_status === 'MATURED';
  const isExpiring = instrument.validity_status === 'EXPIRING_SOON';

  const handleTriggerVerification = async () => {
    try {
      setVerifying(true);
      await triggerInstrumentVerification(instrument.id);
      onRefresh();
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, category: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      await uploadInstrumentDocument(instrument.id, category, file);
      onRefresh();
    } catch (err: any) {
      alert(`Document upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleInitiateRenewal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMaturityDate) return;
    try {
      setRenewalSubmitting(true);
      await initiateRenewal({
        original_instrument_id: instrument.id,
        new_maturity_date: newMaturityDate,
        notes: renewalNotes,
      });
      setShowRenewalModal(false);
      onRefresh();
    } catch (err: any) {
      alert(`Renewal initiation failed: ${err.message}`);
    } finally {
      setRenewalSubmitting(false);
    }
  };

  const handleSubmitRelease = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setReleaseSubmitting(true);
      await submitReleaseRequest({
        instrument_id: instrument.id,
        request_type: 'FULL_RELEASE',
        reason: `Release/refund requested by institution. Beneficiary: ${releaseBeneficiary || 'Not provided'}; account: ${releaseBankAccount || 'Not provided'}; IFSC: ${releaseBankIfsc || 'Not provided'}.`,
        conditions_checklist: {},
      });
      setShowReleaseModal(false);
      onRefresh();
    } catch (err: any) {
      alert(`Release request submission failed: ${err.message}`);
    } finally {
      setReleaseSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Navigation & Action Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={onBack}
              className="p-2 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors mt-0.5 cursor-pointer"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-mono font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                  {instrument.instrument_type}
                </span>
                <h2 className="text-xl font-black text-slate-900 tracking-tight font-mono">
                  {instrument.instrument_number}
                </h2>
                {/* Validity Pill */}
                {isMatured ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800">
                    Matured ({Math.abs(days)}d Overdue)
                  </span>
                ) : isExpiring ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 animate-pulse">
                    Expiring Soon ({days}d Left)
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                    Active & Valid ({days}d)
                  </span>
                )}
                {/* Lifecycle Pill */}
                <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-blue-100 text-blue-900">
                  {instrument.lifecycle_status}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-slate-400" />
                <span className="font-semibold text-slate-700">{instrument.institution?.name}</span>
                <span>·</span>
                <span className="font-mono text-slate-500">{instrument.institution?.aicte_permanent_id}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleTriggerVerification}
              disabled={verifying}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-700 hover:bg-blue-800 text-white font-bold text-xs rounded-lg transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
              <span>{verifying ? 'Verifying...' : 'Trigger Verification'}</span>
            </button>

            {instrument.lifecycle_status !== 'RELEASED' && instrument.lifecycle_status !== 'SUPERSEDED' && (
              <>
                <button
                  type="button"
                  onClick={() => setShowRenewalModal(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold text-xs rounded-lg transition-colors border border-amber-300 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Initiate Renewal</span>
                </button>

                <button
                  type="button"
                  onClick={() => setShowReleaseModal(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-emerald-100 hover:bg-emerald-200 text-emerald-900 font-bold text-xs rounded-lg transition-colors border border-emerald-300 cursor-pointer"
                >
                  <ArrowUpRight className="w-3.5 h-3.5" />
                  <span>Request Release/Refund</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Amount & Key Metrics Strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-5 border-t border-slate-100">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Principal Deposit</span>
            <p className="text-xl font-extrabold text-slate-900 mt-0.5">
              {instrument.formatted_amount || `₹${instrument.amount.toLocaleString('en-IN')}`}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Issuing Bank</span>
            <p className="text-sm font-bold text-slate-800 mt-0.5">{instrument.issuing_bank}</p>
            <p className="text-[10px] text-slate-500">{instrument.branch_name || 'Main Branch'}</p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Maturity Date</span>
            <p className="text-sm font-bold text-slate-800 mt-0.5">{instrument.maturity_date}</p>
            <p className="text-[10px] text-slate-500">Issued: {instrument.issue_date}</p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Joint Lien Endorsement</span>
            <p className="text-xs font-bold text-blue-900 mt-0.5 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-700" />
              <span>{instrument.lien_marked_to || 'Regional Officer, AICTE'}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs Header */}
      <div className="flex items-center space-x-1 border-b border-slate-200 bg-white px-4 rounded-t-xl">
        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors cursor-pointer ${
            activeTab === 'overview'
              ? 'border-blue-700 text-blue-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Overview & Linkages
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('documents')}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
            activeTab === 'documents'
              ? 'border-blue-700 text-blue-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Supporting Documents</span>
          <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded-full text-[10px]">
            {instrument.documents?.length || 0}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('discrepancies')}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
            activeTab === 'discrepancies'
              ? 'border-blue-700 text-blue-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Extracted Data & Discrepancies</span>
          {(instrument.verification_records || []).some(r => r.status === 'WARNING' || r.status === 'FAILED') && (
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('verification')}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors cursor-pointer ${
            activeTab === 'verification'
              ? 'border-blue-700 text-blue-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Verification Findings ({instrument.verification_records?.length || 0})
        </button>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-white p-6 rounded-b-xl border border-t-0 border-slate-200">
          {/* Instrument Parameters */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">
              Deposit Instrument Specifications
            </h3>
            <dl className="grid grid-cols-2 gap-y-3 text-xs">
              <dt className="text-slate-500">Instrument Type:</dt>
              <dd className="font-semibold text-slate-800">{instrument.instrument_type}</dd>
              <dt className="text-slate-500">Instrument Number:</dt>
              <dd className="font-mono font-bold text-slate-900">{instrument.instrument_number}</dd>
              <dt className="text-slate-500">Issuing Bank:</dt>
              <dd className="font-semibold text-slate-800">{instrument.issuing_bank}</dd>
              <dt className="text-slate-500">Branch Name:</dt>
              <dd className="text-slate-800">{instrument.branch_name || 'N/A'}</dd>
              <dt className="text-slate-500">IFSC Code:</dt>
              <dd className="font-mono text-slate-800">{instrument.branch_ifsc || 'N/A'}</dd>
              <dt className="text-slate-500">Account Number:</dt>
              <dd className="font-mono text-slate-800">{instrument.account_number || 'N/A'}</dd>
              <dt className="text-slate-500">Principal Deposit:</dt>
              <dd className="font-black text-slate-900">{instrument.formatted_amount}</dd>
              <dt className="text-slate-500">Effective Issue Date:</dt>
              <dd className="text-slate-800">{instrument.issue_date}</dd>
              <dt className="text-slate-500">Statutory Maturity Date:</dt>
              <dd className="text-slate-800 font-bold">{instrument.maturity_date}</dd>
              <dt className="text-slate-500">Joint Holder Name:</dt>
              <dd className="text-slate-800">{instrument.joint_holder_name || 'None'}</dd>
              <dt className="text-slate-500">Regulatory Purpose:</dt>
              <dd className="text-slate-800">{instrument.purpose || 'Statutory AICTE Corpus'}</dd>
            </dl>
          </div>

          {/* Institution Information & Linkages */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">
              Linked Institution Details
            </h3>
            <dl className="grid grid-cols-2 gap-y-3 text-xs">
              <dt className="text-slate-500">Permanent AICTE ID:</dt>
              <dd className="font-mono font-bold text-blue-700">
                {instrument.institution?.aicte_permanent_id}
              </dd>
              <dt className="text-slate-500">Institution Name:</dt>
              <dd className="font-semibold text-slate-800">{instrument.institution?.name}</dd>
              <dt className="text-slate-500">Type of Institution:</dt>
              <dd className="text-slate-800">{instrument.institution?.institution_type}</dd>
              <dt className="text-slate-500">State & District:</dt>
              <dd className="text-slate-800">{instrument.institution?.district}, {instrument.institution?.state}</dd>
              <dt className="text-slate-500">Contact Email:</dt>
              <dd className="text-slate-800">{instrument.institution?.contact_email || 'N/A'}</dd>
              <dt className="text-slate-500">Contact Phone:</dt>
              <dd className="text-slate-800">{instrument.institution?.contact_phone || 'N/A'}</dd>
            </dl>

            {/* Parent Linkage */}
            {instrument.original_instrument_id && (
              <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200 text-xs">
                <span className="font-bold text-blue-900 block">Replacement Chain Linkage</span>
                <p className="text-blue-800 mt-0.5">
                  This instrument was issued as a statutory replacement for older instrument ID #{instrument.original_instrument_id}.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Supporting Documents */}
      {activeTab === 'documents' && (
        <div className="bg-white p-6 rounded-b-xl border border-t-0 border-slate-200 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Mandatory Supporting Documents</h3>
              <p className="text-xs text-slate-500">
                AICTE mandates FDR receipt certificate, bank lien marked endorsement letter, and joint-holdership declaration.
              </p>
            </div>

            <label className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-xs rounded-lg transition-colors border border-blue-200 cursor-pointer">
              <Upload className="w-3.5 h-3.5" />
              <span>{uploading ? 'Uploading...' : 'Upload Supporting File'}</span>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => handleFileUpload(e, 'FDR_RECEIPT')}
                disabled={uploading}
              />
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(instrument.documents || []).length === 0 ? (
              <div className="col-span-2 p-8 text-center text-slate-400 text-xs">
                No supporting documents uploaded for this instrument yet.
              </div>
            ) : (
              (instrument.documents || []).map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 rounded-xl border border-slate-200 hover:border-blue-300 transition-all flex flex-col justify-between space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 bg-blue-50 text-blue-700 rounded-lg shrink-0">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                          {doc.document_category}
                        </span>
                        <h4 className="text-xs font-bold text-slate-900 mt-1 truncate max-w-xs">
                          {doc.original_filename}
                        </h4>
                        <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                          {(doc.file_size_bytes / 1024).toFixed(1)} KB · {doc.mime_type}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-2.5 rounded-lg text-[10px] text-slate-600 font-mono break-all">
                    <span className="text-slate-400 font-sans block text-[9px] uppercase font-bold">SHA-256 Checksum:</span>
                    {doc.sha256_hash}
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                    <span className={`inline-flex items-center gap-1 font-semibold text-[11px] ${
                      doc.ocr_performed ? 'text-emerald-700' : 'text-slate-500'
                    }`}>
                      {doc.ocr_performed ? <Check className="w-3.5 h-3.5" /> : null}
                      <span>{doc.ocr_performed ? 'OCR Parsed' : 'Text Extracted'}</span>
                    </span>

                    <button
                      type="button"
                      onClick={() => setSelectedDocForViewer(doc)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-bold transition-colors cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Inspect Document</span>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Extracted Data & Discrepancies */}
      {activeTab === 'discrepancies' && (
        <div className="bg-white p-6 rounded-b-xl border border-t-0 border-slate-200 space-y-6">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Extracted OCR Fields vs Recorded Ledger</h3>
            <p className="text-xs text-slate-500">
              Cross-verification between uploaded scan artifacts and institutional database records.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Field Attribute</th>
                  <th className="py-2.5 px-4">Recorded in AICTE Portal</th>
                  <th className="py-2.5 px-4">Extracted from Document Scan</th>
                  <th className="py-2.5 px-4">Verification Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <tr>
                  <td className="py-3 px-4 font-bold text-slate-800">Instrument Number</td>
                  <td className="py-3 px-4 font-mono">{instrument.instrument_number}</td>
                  <td className="py-3 px-4 font-mono">{instrument.instrument_number}</td>
                  <td className="py-3 px-4 text-emerald-700 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Match
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-bold text-slate-800">Issuing Bank</td>
                  <td className="py-3 px-4">{instrument.issuing_bank}</td>
                  <td className="py-3 px-4">{instrument.issuing_bank}</td>
                  <td className="py-3 px-4 text-emerald-700 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Match
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-bold text-slate-800">Principal Amount</td>
                  <td className="py-3 px-4 font-bold">{instrument.formatted_amount}</td>
                  <td className="py-3 px-4 font-bold">{instrument.formatted_amount}</td>
                  <td className="py-3 px-4 text-emerald-700 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Match
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-bold text-slate-800">Maturity Date</td>
                  <td className="py-3 px-4">{instrument.maturity_date}</td>
                  <td className="py-3 px-4">{instrument.maturity_date}</td>
                  <td className="py-3 px-4 text-emerald-700 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Match
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Verification Findings */}
      {activeTab === 'verification' && (
        <div className="bg-white p-6 rounded-b-xl border border-t-0 border-slate-200 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Automated Verification Findings</h3>
            <p className="text-xs text-slate-500">
              Regulatory compliance engine audit results for this security deposit instrument.
            </p>
          </div>

          <div className="space-y-3">
            {(instrument.verification_records || []).length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No automated verification records generated yet. Click "Trigger Verification" to run checks.
              </div>
            ) : (
              (instrument.verification_records || []).map((rec) => (
                <div
                  key={rec.id}
                  className={`p-4 rounded-xl border text-xs ${
                    rec.status === 'PASSED'
                      ? 'bg-emerald-50/30 border-emerald-200 text-emerald-950'
                      : rec.status === 'WARNING'
                      ? 'bg-amber-50/40 border-amber-300 text-amber-950'
                      : rec.status === 'FAILED'
                      ? 'bg-rose-50/40 border-rose-300 text-rose-950'
                      : 'bg-slate-50 border-slate-200 text-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {rec.status === 'PASSED' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      ) : rec.status === 'WARNING' ? (
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-rose-600" />
                      )}
                      <span className="font-bold">{rec.check_type}</span>
                    </div>
                    <span className="font-bold text-[10px] uppercase px-2 py-0.5 rounded bg-white/80 border">
                      {rec.status}
                    </span>
                  </div>

                  <p className="mt-2 text-slate-700">
                    {rec.discrepancy_details || 'Check completed successfully with no anomalies.'}
                  </p>

                  <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-500">
                    <span>Source: {rec.verification_source} {rec.is_simulated ? '(Simulated Registry)' : ''}</span>
                    <span>Recorded: {rec.created_at}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Document Canvas Viewer Modal Integration */}
      {selectedDocForViewer && (
        <DocumentViewerModal
          isOpen={true}
          onClose={() => setSelectedDocForViewer(null)}
          documentTitle={selectedDocForViewer.original_filename}
          categoryCode={selectedDocForViewer.document_category}
          streamUrl={`/api/documents/${selectedDocForViewer.id}/stream`}
          mimeType={selectedDocForViewer.mime_type}
          extractedText={selectedDocForViewer.extracted_text}
          documentId={selectedDocForViewer.id}
          verificationSource="AICTE NIDHI Security Deposit Vault"
          verificationStatus={instrument.verification_status}
        />
      )}

      {/* Renewal Modal */}
      {showRenewalModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-base font-bold text-slate-900">Initiate Deposit Renewal</h3>
            <p className="text-xs text-slate-500 mt-1">
              Extend tenure or link replacement FDR for {instrument.instrument_number}.
            </p>

            <form onSubmit={handleInitiateRenewal} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  New Statutory Maturity Date *
                </label>
                <input
                  type="date"
                  required
                  value={newMaturityDate}
                  onChange={(e) => setNewMaturityDate(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Officer Remarks / Reference
                </label>
                <textarea
                  rows={3}
                  value={renewalNotes}
                  onChange={(e) => setRenewalNotes(e.target.value)}
                  placeholder="Reason for renewal or extension instruction..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                ></textarea>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRenewalModal(false)}
                  className="px-3 py-2 text-xs text-slate-600 font-semibold hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={renewalSubmitting}
                  className="px-4 py-2 text-xs bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg cursor-pointer"
                >
                  {renewalSubmitting ? 'Submitting...' : 'Submit Renewal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Release Request Modal */}
      {showReleaseModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-base font-bold text-slate-900">Request Deposit Release / Refund</h3>
            <p className="text-xs text-slate-500 mt-1">
              Submit formal release clearance for {instrument.instrument_number} ({instrument.formatted_amount}).
            </p>

            <form onSubmit={handleSubmitRelease} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Beneficiary Account Number
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 9876543210123"
                  value={releaseBankAccount}
                  onChange={(e) => setReleaseBankAccount(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Branch IFSC Code
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. SBIN0001234"
                  value={releaseBankIfsc}
                  onChange={(e) => setReleaseBankIfsc(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Beneficiary Name (Trust / Society / Institution)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Saraswati Education Trust"
                  value={releaseBeneficiary}
                  onChange={(e) => setReleaseBeneficiary(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReleaseModal(false)}
                  className="px-3 py-2 text-xs text-slate-600 font-semibold hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={releaseSubmitting}
                  className="px-4 py-2 text-xs bg-emerald-700 hover:bg-emerald-800 text-white font-bold rounded-lg cursor-pointer"
                >
                  {releaseSubmitting ? 'Submitting...' : 'Submit Release Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};


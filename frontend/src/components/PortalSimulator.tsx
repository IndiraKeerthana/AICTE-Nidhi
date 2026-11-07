import React, { useState } from 'react';
import {
  Terminal,
  Send,
  RefreshCw,
  FileCheck,
  Upload,
  Copy,
  Check,
  AlertCircle,
  ExternalLink,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';

export const PortalSimulator: React.FC = () => {
  const [apiKey, setApiKey] = useState('nidhi-integration-demo-key-2026');
  const [idempotencyKey, setIdempotencyKey] = useState(`idemp-${Date.now().toString().slice(-6)}`);
  const [aicteId, setAicteId] = useState('1-9988776655');
  const [instName, setInstName] = useState('Sample Institute of Technology');
  const [declaredIntake, setDeclaredIntake] = useState(120);
  const [category, setCategory] = useState('INCREASE_INTAKE');

  const [activeTab, setActiveTab] = useState<'submit' | 'status' | 'report' | 'rectify'>('submit');
  const [trackingId, setTrackingId] = useState<string>('');
  const [responseLog, setResponseLog] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // File for rectification
  const [rectDocCategory, setRectDocCategory] = useState('LAND_TITLE_DEED');
  const [rectFile, setRectFile] = useState<File | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 1. Submit Application via Integration API
  const handleSubmitApplication = async () => {
    setLoading(true);
    setResponseLog(null);
    try {
      const res = await fetch('/api/integration/v1/applications', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Integration-Key': apiKey,
          'X-Correlation-ID': `corr-${Date.now()}`,
          'X-Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify({
          institution_aicte_id: aicteId,
          institution_name: instName,
          application_category: category,
          academic_year: '2026-2027',
          declared_programme: 'ENGINEERING_AND_TECHNOLOGY',
          declared_course: 'Computer Science & Engineering',
          declared_intake: Number(declaredIntake),
          declared_land_acres: 8.25,
        }),
      });
      const data = await res.json();
      setResponseLog({ status_code: res.status, headers: Object.fromEntries(res.headers.entries()), data });
      if (data.tracking_id) {
        setTrackingId(data.tracking_id);
      }
    } catch (err: any) {
      setResponseLog({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  // 2. Poll Status
  const handleQueryStatus = async () => {
    if (!trackingId) return;
    setLoading(true);
    setResponseLog(null);
    try {
      const res = await fetch(`/api/integration/v1/applications/${trackingId}/status`, {
        headers: { 'X-Integration-Key': apiKey },
      });
      const data = await res.json();
      setResponseLog({ status_code: res.status, data });
    } catch (err: any) {
      setResponseLog({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  // 3. Query Scrutiny Report
  const handleQueryReport = async () => {
    if (!trackingId) return;
    setLoading(true);
    setResponseLog(null);
    try {
      const res = await fetch(`/api/integration/v1/applications/${trackingId}/report`, {
        headers: { 'X-Integration-Key': apiKey },
      });
      const data = await res.json();
      setResponseLog({ status_code: res.status, data });
    } catch (err: any) {
      setResponseLog({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  // 4. Submit Rectification
  const handleSubmitRectification = async () => {
    if (!trackingId || !rectFile) {
      alert('Please enter tracking ID and select a replacement PDF file.');
      return;
    }
    setLoading(true);
    setResponseLog(null);
    try {
      const formData = new FormData();
      formData.append('document_category', rectDocCategory);
      formData.append('file', rectFile);

      const res = await fetch(`/api/integration/v1/applications/${trackingId}/rectifications`, {
        method: 'POST',
        headers: { 'X-Integration-Key': apiKey },
        body: formData,
      });
      const data = await res.json();
      setResponseLog({ status_code: res.status, data });
    } catch (err: any) {
      setResponseLog({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const curlCommand = `curl -X POST http://127.0.0.1:8000/api/integration/v1/applications \\
  -H "Content-Type: application/json" \\
  -H "X-Integration-Key: ${apiKey}" \\
  -H "X-Idempotency-Key: ${idempotencyKey}" \\
  -d '{"institution_aicte_id": "${aicteId}", "institution_name": "${instName}", "application_category": "${category}", "declared_intake": ${declaredIntake}}'`;

  return (
    <div className="space-y-6">
      {/* Prominent Demo Integration Banner Required by Specification */}
      <div className="bg-amber-500/10 border-2 border-amber-500/30 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ShieldAlert className="w-6 h-6 text-amber-500 shrink-0" />
          <div>
            <h3 className="font-extrabold text-amber-900 text-sm tracking-wide uppercase">
              DEMO INTEGRATION — NOT CONNECTED TO AICTE PRODUCTION
            </h3>
            <p className="text-xs text-amber-800/90 mt-0.5">
              Simulates bi-directional REST interoperability between external state/institution portals and AICTE NIDHI's verification engine.
            </p>
          </div>
        </div>
        <span className="text-[11px] font-mono bg-amber-500/20 text-amber-900 px-3 py-1 rounded-full font-bold border border-amber-500/30">
          API v1.0 Adapter
        </span>
      </div>

      {/* Grid: Request Panel & Response Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Interactive Controls */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h2 className="text-base font-bold text-slate-800 mb-4 flex items-center justify-between">
              <span>Integration Action Simulator</span>
              <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                API Key Auth
              </span>
            </h2>

            {/* API Key Configuration */}
            <div className="space-y-3 mb-5 pb-4 border-b border-slate-100 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">X-Integration-Key Header</label>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full font-mono bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">X-Idempotency-Key Header</label>
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={idempotencyKey}
                    onChange={(e) => setIdempotencyKey(e.target.value)}
                    className="w-full font-mono bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800"
                  />
                  <button
                    onClick={() => setIdempotencyKey(`idemp-${Date.now().toString().slice(-6)}`)}
                    className="px-2.5 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded text-slate-700 font-medium"
                    title="Generate new idempotency token"
                  >
                    Regen
                  </button>
                </div>
              </div>
            </div>

            {/* Action Tabs */}
            <div className="flex border-b border-slate-200 mb-4 space-x-4 text-xs font-semibold">
              <button
                onClick={() => setActiveTab('submit')}
                className={`pb-2 border-b-2 transition-colors ${
                  activeTab === 'submit' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                1. Submit App
              </button>
              <button
                onClick={() => setActiveTab('status')}
                className={`pb-2 border-b-2 transition-colors ${
                  activeTab === 'status' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                2. Poll Status
              </button>
              <button
                onClick={() => setActiveTab('report')}
                className={`pb-2 border-b-2 transition-colors ${
                  activeTab === 'report' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                3. Fetch Scrutiny Report
              </button>
              <button
                onClick={() => setActiveTab('rectify')}
                className={`pb-2 border-b-2 transition-colors ${
                  activeTab === 'rectify' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                4. Rectify Document
              </button>
            </div>

            {/* Tab 1: Submit Application */}
            {activeTab === 'submit' && (
              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Institution AICTE ID</label>
                  <input
                    type="text"
                    value={aicteId}
                    onChange={(e) => setAicteId(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Institution Name</label>
                  <input
                    type="text"
                    value={instName}
                    onChange={(e) => setInstName(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Category</label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-medium"
                    >
                      <option value="INCREASE_INTAKE">INCREASE_INTAKE</option>
                      <option value="NEW_INSTITUTE">NEW_INSTITUTE</option>
                      <option value="EOA_REGULAR">EOA_REGULAR</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Declared Intake</label>
                    <input
                      type="number"
                      value={declaredIntake}
                      onChange={(e) => setDeclaredIntake(Number(e.target.value))}
                      className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-bold text-blue-600"
                    />
                  </div>
                </div>

                <button
                  onClick={handleSubmitApplication}
                  disabled={loading}
                  className="w-full mt-4 flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg shadow-sm transition-all"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{loading ? 'Submitting to Adapter...' : 'Dispatch Application Submission Event'}</span>
                </button>
              </div>
            )}

            {/* Tab 2: Poll Status */}
            {activeTab === 'status' && (
              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Tracking ID</label>
                  <input
                    type="text"
                    value={trackingId}
                    onChange={(e) => setTrackingId(e.target.value)}
                    placeholder="e.g. TRK-ABC123XYZ"
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-mono font-bold"
                  />
                </div>
                <button
                  onClick={handleQueryStatus}
                  disabled={loading || !trackingId}
                  className="w-full mt-2 flex items-center justify-center space-x-2 bg-slate-800 hover:bg-slate-900 text-white font-semibold py-2.5 rounded-lg shadow-sm transition-all disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>Poll Scrutiny Processing Status</span>
                </button>
              </div>
            )}

            {/* Tab 3: Scrutiny Report */}
            {activeTab === 'report' && (
              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Tracking ID</label>
                  <input
                    type="text"
                    value={trackingId}
                    onChange={(e) => setTrackingId(e.target.value)}
                    placeholder="e.g. TRK-ABC123XYZ"
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-mono font-bold"
                  />
                </div>
                <button
                  onClick={handleQueryReport}
                  disabled={loading || !trackingId}
                  className="w-full mt-2 flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-lg shadow-sm transition-all disabled:opacity-50"
                >
                  <FileCheck className="w-3.5 h-3.5" />
                  <span>Fetch Official Scrutiny Report via Integration API</span>
                </button>
              </div>
            )}

            {/* Tab 4: Rectification */}
            {activeTab === 'rectify' && (
              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Tracking ID</label>
                  <input
                    type="text"
                    value={trackingId}
                    onChange={(e) => setTrackingId(e.target.value)}
                    placeholder="TRK-..."
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Rectified Document Category</label>
                  <select
                    value={rectDocCategory}
                    onChange={(e) => setRectDocCategory(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-slate-800 font-medium"
                  >
                    <option value="LAND_TITLE_DEED">Land Title Deed (LAND_TITLE_DEED)</option>
                    <option value="FIRE_SAFETY_NOC">Fire Safety NOC (FIRE_SAFETY_NOC)</option>
                    <option value="AFFILIATION_LETTER">University Affiliation Letter</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Replacement File (PDF)</label>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg"
                    onChange={(e) => setRectFile(e.target.files?.[0] || null)}
                    className="w-full text-slate-600 border border-slate-200 rounded px-2 py-1.5 file:mr-3 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                </div>
                <button
                  onClick={handleSubmitRectification}
                  disabled={loading || !trackingId || !rectFile}
                  className="w-full mt-2 flex items-center justify-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 rounded-lg shadow-sm transition-all disabled:opacity-50"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Submit Rectification & Re-run Scrutiny</span>
                </button>
              </div>
            )}
          </div>

          {/* cURL Command Reference */}
          <div className="bg-slate-900 rounded-xl p-4 text-white text-xs font-mono shadow-sm border border-slate-800">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <div className="flex items-center space-x-1.5">
                <Terminal className="w-3.5 h-3.5 text-blue-400" />
                <span className="font-semibold text-slate-300">Equivalent Terminal Command</span>
              </div>
              <button
                onClick={() => copyToClipboard(curlCommand)}
                className="flex items-center space-x-1 text-slate-400 hover:text-white transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="text-[10px]">{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre className="text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
              {curlCommand}
            </pre>
          </div>
        </div>

        {/* Right: Live API Response Inspector */}
        <div className="lg:col-span-6">
          <div className="bg-slate-950 text-slate-100 rounded-xl shadow-lg border border-slate-800 p-5 h-full flex flex-col font-mono text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="font-bold text-slate-200">Live Integration Response Payload</span>
              </div>
              {responseLog && (
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  responseLog.status_code === 200 || responseLog.status_code === 201
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}>
                  HTTP {responseLog.status_code || 'ERROR'}
                </span>
              )}
            </div>

            <div className="flex-1 overflow-auto bg-slate-900/60 rounded-lg p-3 text-slate-300">
              {responseLog ? (
                <pre className="whitespace-pre-wrap text-[11px] leading-relaxed">
                  {JSON.stringify(responseLog, null, 2)}
                </pre>
              ) : (
                <div className="h-48 flex flex-col items-center justify-center text-slate-500 space-y-2">
                  <Terminal className="w-8 h-8 opacity-40" />
                  <p className="text-xs">Select an integration action on the left to inspect live backend responses.</p>
                </div>
              )}
            </div>

            {/* Idempotency Notification */}
            {responseLog?.data?.is_duplicate_event && (
              <div className="mt-3 p-2.5 bg-blue-500/10 border border-blue-500/30 rounded text-[11px] text-blue-300 flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-blue-400 shrink-0" />
                <span>
                  <strong>Idempotent Event Handled:</strong> Repeated event deduplicated without creating duplicate records.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

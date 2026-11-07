import React, { useState, useEffect } from 'react';
import {
  Building,
  Search,
  Landmark,
  ShieldCheck,
  RefreshCw,
  ExternalLink,
  MapPin,
  Mail,
  Phone
} from 'lucide-react';
import { Institution } from '../types';
import { fetchInstitutions } from '../services/api';

interface InstitutionsDirectoryViewProps {
  onSelectInstitutionFilter?: (institutionId: number) => void;
}

export const InstitutionsDirectoryView: React.FC<InstitutionsDirectoryViewProps> = ({
  onSelectInstitutionFilter,
}) => {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const loadInstitutions = async () => {
    try {
      setLoading(true);
      const data = await fetchInstitutions();
      setInstitutions(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInstitutions();
  }, []);

  const filtered = institutions.filter((inst) => {
    if (!searchTerm) return true;
    const q = searchTerm.toLowerCase();
    return (
      inst.name.toLowerCase().includes(q) ||
      inst.aicte_permanent_id.toLowerCase().includes(q) ||
      (inst.state || '').toLowerCase().includes(q) ||
      (inst.district || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Building className="w-5 h-5 text-sky-600" />
            <span>AICTE NIDHI Technical Institutions Directory</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Directory of approved institutions, permanent AICTE IDs, regional jurisdictions, and security deposit encumbrances.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search institutions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-60"
            />
          </div>

          <button
            type="button"
            onClick={loadInstitutions}
            className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors border border-slate-200 cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Grid of Institutions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.length === 0 ? (
          <div className="col-span-3 p-12 text-center text-slate-400 text-xs bg-white rounded-xl border border-slate-200">
            No institutions matching search criteria.
          </div>
        ) : (
          filtered.map((inst) => (
            <div
              key={inst.id}
              className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs hover:border-blue-400 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[10px] font-mono font-bold bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                    {inst.aicte_permanent_id}
                  </span>
                  <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-semibold">
                    {inst.institution_type || 'TECHNICAL'}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-slate-900 mt-2 line-clamp-2">
                  {inst.name}
                </h3>

                <p className="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span>{inst.district}, {inst.state}</span>
                </p>

                {inst.contact_email && (
                  <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5 truncate">
                    <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{inst.contact_email}</span>
                  </p>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500 text-[11px]">
                  Enrolled under AICTE Joint Lien
                </span>
                {onSelectInstitutionFilter && (
                  <button
                    type="button"
                    onClick={() => onSelectInstitutionFilter(inst.id)}
                    className="text-blue-700 font-bold hover:underline cursor-pointer"
                  >
                    View FDRs &rarr;
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};


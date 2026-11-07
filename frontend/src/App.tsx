import React, { useState, useEffect } from 'react';
import { Sidebar, NavView } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardOverview } from './components/DashboardOverview';
import { InstrumentRegister } from './components/InstrumentRegister';
import { InstrumentDetails } from './components/InstrumentDetails';
import { RenewalsView } from './components/RenewalsView';
import { ReleaseRefundView } from './components/ReleaseRefundView';
import { NotificationsView } from './components/NotificationsView';
import { ReportsView } from './components/ReportsView';
import { InstitutionsDirectoryView } from './components/InstitutionsDirectoryView';
import { SystemAdminView } from './components/SystemAdminView';
import {
  DepositInstrument,
  InstrumentDetail,
  DashboardMetrics,
  UserInfo
} from './types';
import {
  fetchDashboardMetrics,
  fetchInstruments,
  fetchInstrumentDetail,
  generateReminders,
  setSessionAuth
} from './services/api';

const DEFAULT_USERS: UserInfo[] = [
  {
    username: 'officer1',
    full_name: 'Regulation Officer',
    role: 'OFFICER',
    designation: 'Regulation Bureau Officer',
    institution_id: null,
    email: 'officer@aicte-india.org'
  },
  {
    username: 'approver1',
    full_name: 'Prof. R. K. Verma',
    role: 'APPROVER',
    designation: 'Bureau Head / Regional Director',
    institution_id: null,
    email: 'rk.verma@aicte-india.org'
  },
  {
    username: 'admin1',
    full_name: 'AICTE System Administrator',
    role: 'ADMIN',
    designation: 'Deposit Portal Administrator',
    institution_id: null,
    email: 'admin@aicte-india.org'
  }
];

export function App() {
  const [currentView, setCurrentView] = useState<NavView>('dashboard');
  const [currentUser, setCurrentUser] = useState<UserInfo>(DEFAULT_USERS[0]);
  const [availableUsers, setAvailableUsers] = useState<UserInfo[]>(DEFAULT_USERS);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [instruments, setInstruments] = useState<DepositInstrument[]>([]);
  const [selectedInstrumentId, setSelectedInstrumentId] = useState<number | null>(null);
  const [selectedInstrumentDetail, setSelectedInstrumentDetail] = useState<InstrumentDetail | null>(null);
  const [registerFilters, setRegisterFilters] = useState<{ validity?: string; lifecycle?: string; bank?: string } | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  // Set session auth whenever currentUser changes
  useEffect(() => {
    setSessionAuth(currentUser.role, currentUser.username, currentUser.institution_id);
    loadAllData();
  }, [currentUser]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      const [m, insts] = await Promise.all([
        fetchDashboardMetrics(),
        fetchInstruments(),
      ]);
      setMetrics(m);
      setInstruments(insts);
    } catch (err) {
      console.error('Failed to load initial data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load detailed instrument if selected
  const loadDetail = async (id: number) => {
    try {
      const detail = await fetchInstrumentDetail(id);
      setSelectedInstrumentDetail(detail);
    } catch (err) {
      console.error(err);
      setSelectedInstrumentDetail(null);
    }
  };

  useEffect(() => {
    if (selectedInstrumentId) {
      loadDetail(selectedInstrumentId);
    } else {
      setSelectedInstrumentDetail(null);
    }
  }, [selectedInstrumentId]);

  // Handle Switch User / Role
  const handleSwitchUser = (user: UserInfo) => {
    setCurrentUser(user);
    setSelectedInstrumentId(null);
  };

  // Handle Trigger Reminders
  const handleTriggerReminders = async () => {
    await generateReminders();
    await loadAllData();
  };

  const getPageTitle = () => {
    if (selectedInstrumentDetail) {
      return `Instrument Inspection — ${selectedInstrumentDetail.instrument_number} (${selectedInstrumentDetail.issuing_bank})`;
    }
    switch (currentView) {
      case 'dashboard':
        return 'AICTE NIDHI — Security Deposit & FDR Command Center';
      case 'instruments':
        return 'Security Deposit & Fixed Deposit Receipt Register';
      case 'renewals':
        return 'Deposit Renewals & Replacement Queue';
      case 'releases':
        return 'Deposit Release & Refund Governance';
      case 'notifications':
        return 'Maturity Alerts, Overdue Notices & Reminders';
      case 'reports':
        return 'Portfolio Reports & CSV Data Exports';
      case 'institutions':
        return 'AICTE Approved Technical Institutions Directory';
      case 'administration':
        return 'System Administration & Security Settings';
      default:
        return 'AICTE NIDHI';
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100 text-slate-800">
      {/* Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        onNavigate={(view) => {
          setCurrentView(view);
          setSelectedInstrumentId(null);
        }}
        currentUser={currentUser}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Prototype Transparency Banner */}
        <div className="bg-amber-400 text-slate-950 px-4 py-1 text-center text-[11px] font-black tracking-wider flex items-center justify-center gap-2 shadow-xs shrink-0 border-b border-amber-500">
          <span className="inline-block w-2 h-2 rounded-full bg-slate-950 animate-pulse"></span>
          <span>PROTOTYPE · SYNTHETIC DATA ONLY</span>
          <span className="text-[10px] font-semibold text-slate-900 ml-2 hidden sm:inline">
            Demonstration environment for AICTE NIDHI · Security Deposit and FDR Management Portal · Not connected to live banking gateways
          </span>
        </div>

        <Header
          pageTitle={getPageTitle()}
          currentUser={currentUser}
        />

        <main className="flex-1 overflow-y-auto p-6">
          {selectedInstrumentDetail ? (
            <InstrumentDetails
              instrument={selectedInstrumentDetail}
              onBack={() => setSelectedInstrumentId(null)}
              onRefresh={async () => {
                if (selectedInstrumentId) {
                  await loadDetail(selectedInstrumentId);
                  await loadAllData();
                }
              }}
            />
          ) : currentView === 'dashboard' ? (
            <DashboardOverview
              metrics={metrics}
              loading={loading}
              onSelectInstrument={(id) => setSelectedInstrumentId(id)}
              onNavigateToRegister={(filters) => {
                setRegisterFilters(filters);
                setCurrentView('instruments');
              }}
              onTriggerReminders={handleTriggerReminders}
              onRefresh={loadAllData}
            />
          ) : currentView === 'instruments' ? (
            <InstrumentRegister
              instruments={instruments}
              loading={loading}
              initialFilters={registerFilters}
              onSelectInstrument={(id) => setSelectedInstrumentId(id)}
              onRefresh={loadAllData}
            />
          ) : currentView === 'renewals' ? (
            <RenewalsView
              onSelectInstrument={(id) => setSelectedInstrumentId(id)}
            />
          ) : currentView === 'releases' ? (
            <ReleaseRefundView
              currentUser={currentUser}
              onSelectInstrument={(id) => setSelectedInstrumentId(id)}
            />
          ) : currentView === 'notifications' ? (
            <NotificationsView
              onSelectInstrument={(id) => setSelectedInstrumentId(id)}
            />
          ) : currentView === 'reports' ? (
            <ReportsView />
          ) : currentView === 'institutions' ? (
            <InstitutionsDirectoryView
              onSelectInstitutionFilter={(instId) => {
                setRegisterFilters(undefined);
                setCurrentView('instruments');
              }}
            />
          ) : (
            <SystemAdminView />
          )}
        </main>

        {/* Institutional Authority Footer */}
        <footer className="h-8 bg-slate-900 text-slate-300 border-t border-slate-800 px-6 flex items-center justify-between text-xs shrink-0 select-none">
          <div className="flex items-center space-x-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
            <span className="font-semibold text-white tracking-wide">
              Instrument records and verification findings support review. The authorised authority decides.
            </span>
          </div>
          <div className="hidden md:flex items-center space-x-4 text-[11px] text-slate-400">
            <span>AICTE NIDHI · Security Deposit & FDR Management Portal · APH Governance</span>
            <span>&bull;</span>
            <span>Authorised Official: <strong className="text-slate-200">{currentUser.full_name}</strong> ({currentUser.role})</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

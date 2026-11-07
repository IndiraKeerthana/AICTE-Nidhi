import React, { useState, useEffect } from 'react';
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Check,
  ArrowRight,
  RefreshCw,
  Clock,
  Landmark
} from 'lucide-react';
import { NotificationItem } from '../types';
import {
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  generateReminders
} from '../services/api';

interface NotificationsViewProps {
  onSelectInstrument: (id: number) => void;
}

export const NotificationsView: React.FC<NotificationsViewProps> = ({
  onSelectInstrument,
}) => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reminding, setReminding] = useState(false);

  const loadNotifications = async () => {
    try {
      setLoading(true);
      const data = await fetchNotifications();
      setNotifications(data);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const handleMarkRead = async (id: number) => {
    try {
      await markNotificationRead(id);
      await loadNotifications();
    } catch (err: any) {
      alert(`Failed to update notification: ${err.message}`);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      await loadNotifications();
    } catch (err: any) {
      alert(`Failed to mark all as read: ${err.message}`);
    }
  };

  const handleTriggerReminders = async () => {
    try {
      setReminding(true);
      await generateReminders();
      await loadNotifications();
    } catch (err: any) {
      alert(`Reminder scan failed: ${err.message}`);
    } finally {
      setReminding(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
            <Bell className="w-5 h-5 text-amber-600" />
            <span>Maturity Alerts, Overdue Notices & Discrepancy Reminders</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated alerts for instruments within the 30-day renewal threshold, unrenewed matured FDRs, and release approvals.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTriggerReminders}
            disabled={reminding}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition-colors cursor-pointer disabled:opacity-50"
          >
            <Clock className={`w-3.5 h-3.5 ${reminding ? 'animate-spin' : ''}`} />
            <span>Run Automated Scan</span>
          </button>

          {notifications.some((n) => !n.is_read) && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition-colors border border-slate-300 cursor-pointer"
            >
              Mark All Read
            </button>
          )}

          <button
            type="button"
            onClick={loadNotifications}
            className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors border border-slate-200 cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-slate-400 text-xs">Loading notifications...</div>
        ) : notifications.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400 text-xs">
            No active maturity alerts or reminders.
          </div>
        ) : (
          notifications.map((item) => {
            const isCritical = item.severity === 'CRITICAL';
            const isWarning = item.severity === 'WARNING';

            return (
              <div
                key={item.id}
                className={`p-4 rounded-xl border transition-all text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
                  item.is_read
                    ? 'bg-slate-50 border-slate-200 opacity-70'
                    : isCritical
                    ? 'bg-rose-50/60 border-rose-300 shadow-xs'
                    : isWarning
                    ? 'bg-amber-50/50 border-amber-300 shadow-xs'
                    : 'bg-white border-slate-200 shadow-xs'
                }`}
              >
                <div className="flex items-start space-x-3.5 flex-1 min-w-0">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                    isCritical ? 'bg-rose-100 text-rose-700' : isWarning ? 'bg-amber-100 text-amber-700' : 'bg-blue-50 text-blue-700'
                  }`}>
                    {isCritical ? (
                      <ShieldAlert className="w-4 h-4" />
                    ) : (
                      <AlertTriangle className="w-4 h-4" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-slate-900 text-xs">{item.title}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isCritical ? 'bg-rose-100 text-rose-800' : isWarning ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
                      }`}>
                        {item.notification_type}
                      </span>
                      {item.is_read && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-200 text-slate-600 font-semibold">
                          Read
                        </span>
                      )}
                    </div>
                    <p className="text-slate-600 mt-1 leading-relaxed">{item.message}</p>
                    <div className="flex items-center gap-3 text-[10px] text-slate-400 mt-1.5">
                      <span>Triggered: {item.trigger_date}</span>
                      {item.instrument_id && (
                        <span>&bull; FDR Instrument ID: #{item.instrument_id}</span>
                      )}
                      <span>&bull; Role: {item.target_role}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2 shrink-0 self-end sm:self-center">
                  {item.instrument_id && (
                    <button
                      type="button"
                      onClick={() => onSelectInstrument(item.instrument_id!)}
                      className="px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold transition-colors flex items-center space-x-1 text-xs cursor-pointer"
                    >
                      <span>Inspect FDR</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {!item.is_read && (
                    <button
                      type="button"
                      onClick={() => handleMarkRead(item.id)}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700 font-medium transition-colors flex items-center space-x-1 text-xs cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5 text-slate-500" />
                      <span>Mark Read</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

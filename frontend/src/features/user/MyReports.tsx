import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { AlertCircle, ArrowRight, Clock, FileText, ShieldAlert } from 'lucide-react';

interface Report {
  id: string;
  code: string;
  report_type: string;
  category: string;
  description: string | null;
  location: string;
  reporter: string;
  status: string;
  priority: string;
  severity: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  anonymous: boolean;
}

interface History {
  event: string;
  old_value?: string | null;
  new_value?: string | null;
  changed_at: string;
  changed_by: string;
  note?: string | null;
}

const FILTERS = [
  { label: 'All', value: '' },
  { label: 'Emergency', value: 'EMERGENCY' },
  { label: 'Safety', value: 'SAFETY' },
  { label: 'Maintenance', value: 'MAINTENANCE' },
  { label: 'Other', value: 'GENERAL' },
];

function statusClass(status: string): string {
  if (['RESOLVED', 'CLOSED'].includes(status)) return 'badge-green';
  if (['CRITICAL', 'REJECTED', 'CANCELLED'].includes(status)) return 'badge-red';
  if (['IN_PROGRESS', 'RESPONDING', 'INVESTIGATION', 'ASSIGNED'].includes(status)) return 'badge-blue';
  return 'badge-amber';
}

export const MyReports: React.FC = () => {
  const [filter, setFilter] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data: reports = [], isLoading, isError } = useQuery<Report[]>({
    queryKey: ['my-reports', filter],
    queryFn: async () => (await api.get('/reports', { params: filter ? { report_type: filter } : {} })).data,
  });
  const { data: history = [], isLoading: historyLoading, isError: historyError } = useQuery<History[]>({
    queryKey: ['report-history', expanded],
    queryFn: async () => (await api.get(`/reports/${encodeURIComponent(expanded!)}/history`)).data,
    enabled: !!expanded,
  });

  return (
    <section className="max-w-4xl space-y-5">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <div className="section-header"><FileText size={20} className="text-indigo-400" />My Reports</div>
          <p className="text-sm text-slate-400 mt-2">Private updates and report timelines for reports you submitted.</p>
        </div>
        <Link to="/report?type=MAINTENANCE" className="btn-primary flex items-center gap-2">Report a campus issue <ArrowRight size={15} /></Link>
      </header>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {FILTERS.map(item => (
          <button
            key={item.value}
            onClick={() => setFilter(item.value)}
            className={`px-3 py-2 rounded-lg border text-xs whitespace-nowrap ${filter === item.value ? 'border-indigo-500 bg-indigo-900/30 text-indigo-200' : 'border-slate-800 text-slate-400 hover:bg-slate-800'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading your reports…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Unable to load your reports. Please try again.</div>
          : reports.length === 0 ? (
            <div className="card p-10 text-center">
              <FileText size={24} className="text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-300">No reports yet.</p>
              <p className="text-xs text-slate-500 mt-1">If you encounter a campus problem, use Report Campus Issue.</p>
              <Link to="/report?type=MAINTENANCE" className="btn-primary inline-flex mt-4">Report Campus Issue</Link>
            </div>
          ) : (
            <div className="space-y-3">
              {reports.map(report => (
                <article key={report.id} className="card overflow-hidden">
                  <button
                    className="w-full text-left p-4 sm:p-5 hover:bg-slate-800/30"
                    onClick={() => setExpanded(expanded === report.code ? null : report.code)}
                    aria-expanded={expanded === report.code}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-slate-500">{report.code}</span>
                          <span className="badge-blue">{report.report_type}</span>
                          <span className={statusClass(report.status)}>{report.status.replace(/_/g, ' ')}</span>
                        </div>
                        <h2 className="font-semibold text-white mt-2">{report.category}</h2>
                        <p className="text-xs text-slate-400 mt-1">{report.location} · {new Date(report.created_at).toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-2 self-start sm:self-auto">
                        <span className={report.priority === 'CRITICAL' || report.priority === 'HIGH' ? 'badge-red' : 'badge-amber'}>{report.severity || report.priority}</span>
                        <ArrowRight size={15} className={`text-slate-500 transition-transform ${expanded === report.code ? 'rotate-90' : ''}`} />
                      </div>
                    </div>
                  </button>
                  {expanded === report.code && (
                    <div className="border-t border-slate-800 p-4 sm:p-5 space-y-4">
                      {report.report_type === 'SAFETY' && <p className="text-xs text-amber-300 flex items-center gap-2"><ShieldAlert size={14} />Confidential report · {report.anonymous ? 'Submitted anonymously' : 'Visible only to you and authorized safety staff'}</p>}
                      <p className="text-sm text-slate-300 whitespace-pre-wrap">{report.description || 'Report description is unavailable.'}</p>
                      {report.resolved_at && <p className="text-xs text-emerald-300">Resolved {new Date(report.resolved_at).toLocaleString()}</p>}
                      <div>
                        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2"><Clock size={14} />Status timeline</h3>
                        {historyLoading ? <p className="text-xs text-slate-500">Loading timeline…</p>
                          : historyError ? <p role="alert" className="text-xs text-red-300">Unable to load report history.</p>
                            : history.length === 0 ? <p className="text-xs text-slate-500">No history available.</p>
                              : <ol className="border-l border-slate-700 ml-1 space-y-3">
                                {history.map((entry, index) => (
                                  <li key={`${entry.event}-${entry.changed_at}-${index}`} className="pl-4 relative">
                                    <span className="absolute w-2 h-2 rounded-full bg-indigo-400 -left-[5px] top-1.5" />
                                    <p className="text-xs font-medium text-slate-200">{entry.event.replace(/_/g, ' ')}{entry.new_value ? ` · ${entry.new_value.replace(/_/g, ' ')}` : ''}</p>
                                    <p className="text-[11px] text-slate-500 mt-1">{new Date(entry.changed_at).toLocaleString()}</p>
                                  </li>
                                ))}
                              </ol>}
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
    </section>
  );
};

import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { AlertCircle, CheckCircle, Clock, FileText, Siren, ShieldAlert } from 'lucide-react';

interface Report {
  id: string;
  code: string;
  report_type: string;
  category: string;
  description: string;
  location: string;
  reporter: string;
  status: string;
  priority: string;
  severity: string | null;
  assigned_to: string | null;
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

interface Summary {
  total: number;
  open: number;
  critical: number;
  high: number;
  in_progress: number;
  resolved_today: number;
  by_type: Record<string, number>;
  historical_data_available: boolean;
}

const REPORT_TYPES = ['', 'EMERGENCY', 'SAFETY', 'MAINTENANCE', 'GENERAL'];
const STATUSES: Record<string, string[]> = {
  EMERGENCY: ['OPEN', 'ACKNOWLEDGED', 'RESPONDING', 'RESOLVED', 'CANCELLED'],
  SAFETY: ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'INVESTIGATION', 'RESOLVED', 'CLOSED', 'REJECTED'],
  MAINTENANCE: ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'],
  GENERAL: ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'],
};
const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

function statusClass(status: string): string {
  if (['RESOLVED', 'CLOSED'].includes(status)) return 'badge-green';
  if (['CRITICAL', 'REJECTED', 'CANCELLED'].includes(status)) return 'badge-red';
  if (['IN_PROGRESS', 'RESPONDING', 'INVESTIGATION', 'ASSIGNED'].includes(status)) return 'badge-blue';
  return 'badge-amber';
}

export const ActionCenter: React.FC = () => {
  const queryClient = useQueryClient();
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [assignee, setAssignee] = useState('');
  const [priority, setPriority] = useState('');
  const [nextStatus, setNextStatus] = useState('');
  const [resolutionNote, setResolutionNote] = useState('');
  const [note, setNote] = useState('');
  const [feedback, setFeedback] = useState('');

  const params = useMemo(() => ({
    ...(typeFilter ? { report_type: typeFilter } : {}),
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(categoryFilter ? { category: categoryFilter } : {}),
    ...(locationFilter ? { location: locationFilter } : {}),
  }), [typeFilter, statusFilter, categoryFilter, locationFilter]);

  const { data: summary } = useQuery<Summary>({
    queryKey: ['action-summary'],
    queryFn: async () => (await api.get('/reports/summary')).data,
  });
  const { data: reports = [], isLoading, isError } = useQuery<Report[]>({
    queryKey: ['action-reports', params],
    queryFn: async () => (await api.get('/reports', { params })).data,
  });
  const selected = reports.find(report => report.code === selectedCode) || null;

  const { data: history = [], isLoading: historyLoading, isError: historyError } = useQuery<History[]>({
    queryKey: ['report-history', selectedCode, 'management'],
    queryFn: async () => (await api.get(`/reports/${encodeURIComponent(selectedCode!)}/history`)).data,
    enabled: !!selectedCode,
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['action-reports'] }),
      queryClient.invalidateQueries({ queryKey: ['action-summary'] }),
      queryClient.invalidateQueries({ queryKey: ['report-history', selectedCode, 'management'] }),
      queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    ]);
  };
  const updateMutation = useMutation({
    mutationFn: async (body: Record<string, string | undefined>) => api.patch(`/reports/${encodeURIComponent(selectedCode!)}`, body),
    onSuccess: async () => { setFeedback('Report updated and history recorded.'); await refresh(); },
    onError: (error: any) => setFeedback(error?.response?.data?.detail || 'Unable to update report.'),
  });
  const noteMutation = useMutation({
    mutationFn: async (value: string) => api.post(`/reports/${encodeURIComponent(selectedCode!)}/notes`, { note: value }),
    onSuccess: async () => { setNote(''); setFeedback('Internal note added to report history.'); await refresh(); },
    onError: (error: any) => setFeedback(error?.response?.data?.detail || 'Unable to add note.'),
  });

  const submitUpdate = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setFeedback('');
    const fields: Record<string, string | undefined> = {};
    if (nextStatus !== selected.status) fields.status = nextStatus;
    if (assignee !== (selected.assigned_to || '')) fields.assigned_to = assignee;
    const currentPriority = selected.severity || selected.priority;
    if (priority !== currentPriority) fields[selected.report_type === 'SAFETY' || selected.report_type === 'EMERGENCY' ? 'severity' : 'priority'] = priority;
    if (nextStatus === 'RESOLVED' && resolutionNote.trim()) fields.resolution_note = resolutionNote.trim();
    if (Object.keys(fields).length === 0) {
      setFeedback('No changes to save.');
      return;
    }
    updateMutation.mutate(fields);
  };

  return (
    <section className="space-y-5">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Campus Action</p>
        <h1 className="text-2xl font-bold text-white mt-1">Campus Action Center</h1>
        <p className="text-sm text-slate-400 mt-1">Review real campus reports, manage response, and retain an auditable history.</p>
      </header>

      <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
        {[
          { label: 'Open reports', value: summary?.open ?? '—', icon: FileText, style: 'text-indigo-300' },
          { label: 'Critical', value: summary?.critical ?? '—', icon: Siren, style: 'text-red-300' },
          { label: 'High priority', value: summary?.high ?? '—', icon: ShieldAlert, style: 'text-amber-300' },
          { label: 'In progress', value: summary?.in_progress ?? '—', icon: Clock, style: 'text-cyan-300' },
          { label: 'Resolved today', value: summary?.resolved_today ?? '—', icon: CheckCircle, style: 'text-emerald-300' },
        ].map(card => {
          const Icon = card.icon;
          return <div key={card.label} className="stat-card"><div className="stat-icon bg-slate-800"><Icon size={18} className={card.style} /></div><div><p className="text-xs text-slate-500">{card.label}</p><p className={`text-2xl font-bold ${card.style}`}>{card.value}</p></div></div>;
        })}
      </div>

      {summary && !summary.historical_data_available && (
        <p className="text-xs text-slate-500">No historical data available yet. Counts update as reports are submitted.</p>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
        <section className="xl:col-span-3 space-y-4">
          <div className="card p-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
            <select aria-label="Filter report type" className="input-field" value={typeFilter} onChange={event => setTypeFilter(event.target.value)}>
              {REPORT_TYPES.map(type => <option key={type} value={type}>{type || 'All types'}</option>)}
            </select>
            <select aria-label="Filter status" className="input-field" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              {Array.from(new Set(Object.values(STATUSES).flat())).map(status => <option key={status}>{status}</option>)}
            </select>
            <input aria-label="Filter category" className="input-field" placeholder="Filter category" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)} />
            <input aria-label="Filter location" className="input-field" placeholder="Filter location" value={locationFilter} onChange={event => setLocationFilter(event.target.value)} />
          </div>
          {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading campus reports…</div>
            : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Unable to load campus reports.</div>
              : reports.length === 0 ? <div className="card p-10 text-center text-sm text-slate-400">No reports match these filters.</div>
                : <div className="space-y-2">
                  {reports.map(report => (
                    <button key={report.id} onClick={() => {
                      setSelectedCode(report.code);
                      setAssignee(report.assigned_to || '');
                      setPriority(report.severity || report.priority);
                      setNextStatus(report.status);
                      setResolutionNote('');
                      setFeedback('');
                    }} className={`card w-full p-4 text-left hover:border-indigo-600 ${selectedCode === report.code ? 'border-indigo-500 bg-indigo-950/20' : ''}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-slate-400">{report.code}</span>
                        <span className="badge-blue">{report.report_type}</span>
                        <span className={statusClass(report.status)}>{report.status.replace(/_/g, ' ')}</span>
                        <span className={report.priority === 'CRITICAL' || report.priority === 'HIGH' ? 'badge-red' : 'badge-amber'}>{report.severity || report.priority}</span>
                      </div>
                      <p className="font-semibold text-white mt-2">{report.category}</p>
                      <p className="text-xs text-slate-400 mt-1">{report.location} · {report.reporter} · {new Date(report.created_at).toLocaleString()}</p>
                    </button>
                  ))}
                </div>}
        </section>

        <section className="xl:col-span-2">
          {!selected ? <div className="card h-full min-h-64 p-8 flex flex-col items-center justify-center text-center">
            <FileText size={24} className="text-slate-600 mb-3" />
            <p className="text-sm text-slate-300">Select a report to review its details and history.</p>
          </div> : (
            <div className="card p-5 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-mono text-xs text-slate-500">{selected.code}</p><h2 className="text-lg font-bold text-white mt-1">{selected.category}</h2></div>
                {selected.report_type === 'SAFETY' && selected.anonymous && <span className="badge-amber">Anonymous Reporter</span>}
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div><p className="text-slate-500">Type</p><p className="text-slate-200 mt-1">{selected.report_type}</p></div>
                <div><p className="text-slate-500">Location</p><p className="text-slate-200 mt-1">{selected.location}</p></div>
                <div><p className="text-slate-500">Reporter</p><p className="text-slate-200 mt-1">{selected.reporter}</p></div>
                <div><p className="text-slate-500">Reported</p><p className="text-slate-200 mt-1">{new Date(selected.created_at).toLocaleString()}</p></div>
              </div>
              <p className="text-sm text-slate-300 whitespace-pre-wrap border-y border-slate-800 py-4">{selected.description}</p>
              {selected.report_type === 'EMERGENCY' && <p className="text-xs text-red-300">Campus report only; no external emergency service is contacted.</p>}
              <form onSubmit={submitUpdate} className="space-y-3">
                <div>
                  <label className="label" htmlFor="action-status">Status</label>
                  <select id="action-status" className="input-field" value={nextStatus} onChange={event => setNextStatus(event.target.value)}>
                    {STATUSES[selected.report_type].map(status => <option key={status} value={status}>{status.replace(/_/g, ' ')}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="action-priority">{selected.report_type === 'SAFETY' || selected.report_type === 'EMERGENCY' ? 'Severity' : 'Priority'}</label>
                  <select id="action-priority" className="input-field" value={priority} onChange={event => setPriority(event.target.value)}>
                    {PRIORITIES.map(item => <option key={item}>{item}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="action-assignee">Assigned person / team</label>
                  <input id="action-assignee" className="input-field" maxLength={120} value={assignee} onChange={event => setAssignee(event.target.value)} placeholder="e.g. Facilities Team" />
                </div>
                {nextStatus === 'RESOLVED' && (
                  <div><label className="label" htmlFor="resolution-note">Resolution note (visible to reporter)</label><textarea id="resolution-note" className="input-field min-h-20" value={resolutionNote} onChange={event => setResolutionNote(event.target.value)} maxLength={2000} /></div>
                )}
                <button className="btn-primary w-full" disabled={updateMutation.isPending}>{updateMutation.isPending ? 'Saving…' : 'Save report actions'}</button>
              </form>
              <form onSubmit={event => { event.preventDefault(); if (note.trim()) noteMutation.mutate(note.trim()); }} className="space-y-2 border-t border-slate-800 pt-4">
                <label className="label" htmlFor="management-note">Internal management note</label>
                <textarea id="management-note" className="input-field min-h-16" value={note} onChange={event => setNote(event.target.value)} maxLength={2000} placeholder="Visible only to authorized management." />
                <button className="btn-secondary w-full" disabled={!note.trim() || noteMutation.isPending}>{noteMutation.isPending ? 'Adding…' : 'Add internal note'}</button>
              </form>
              {feedback && <p role={updateMutation.isError || noteMutation.isError ? 'alert' : 'status'} className={`text-xs ${updateMutation.isError || noteMutation.isError ? 'text-red-300' : 'text-emerald-300'}`}>{feedback}</p>}
              <div className="border-t border-slate-800 pt-4">
                <h3 className="text-sm font-semibold text-slate-200 mb-3">History & audit</h3>
                {historyLoading ? <p className="text-xs text-slate-500">Loading history…</p>
                  : historyError ? <p role="alert" className="text-xs text-red-300">Unable to load report history.</p>
                    : <ol className="border-l border-slate-700 ml-1 space-y-3 max-h-72 overflow-auto">
                      {history.map((entry, index) => (
                        <li key={`${entry.event}-${entry.changed_at}-${index}`} className="pl-4 relative">
                          <span className="absolute w-2 h-2 rounded-full bg-indigo-400 -left-[5px] top-1.5" />
                          <p className="text-xs font-medium text-slate-200">{entry.event.replace(/_/g, ' ')}{entry.new_value ? ` · ${entry.new_value.replace(/_/g, ' ')}` : ''}</p>
                          {entry.note && <p className="text-xs text-slate-400 mt-1">{entry.note}</p>}
                          <p className="text-[11px] text-slate-600 mt-1">{entry.changed_by} · {new Date(entry.changed_at).toLocaleString()}</p>
                        </li>
                      ))}
                    </ol>}
              </div>
            </div>
          )}
        </section>
      </div>
    </section>
  );
};

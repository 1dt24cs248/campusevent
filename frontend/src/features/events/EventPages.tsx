import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar, MapPin, UserRound } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { CampusEvent } from './eventTypes';
import { EVENT_CATEGORIES, formatEventAudience, formatEventCategory } from './eventTypes';

function EventCard({ event }: { event: CampusEvent }) {
  return (
    <Link to={`/events/${event.id}`} className="card block p-5 hover:border-indigo-700/60 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase text-cyan-300">{formatEventCategory(event.category)}</p>
          <h2 className="text-lg font-semibold text-white mt-1">{event.title}</h2>
        </div>
        <span className="badge-blue">{formatEventAudience(event.audience)}</span>
      </div>
      <p className="text-sm text-slate-300 mt-3 line-clamp-3">{event.description}</p>
      <p className="text-xs text-slate-400 mt-4">{new Date(event.start_dt).toLocaleString()} – {new Date(event.end_dt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>
      <p className="text-xs text-slate-400 mt-2">{event.location || 'Venue not listed'} · {event.organizer || 'Organizer not listed'}</p>
    </Link>
  );
}

export const StudentEvents: React.FC = () => {
  const { user } = useAuth();
  const { data = [], isLoading, isError } = useQuery<CampusEvent[]>({
    queryKey: ['events', user?.id],
    queryFn: async () => (await api.get('/events')).data,
    enabled: Boolean(user?.id),
  });
  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Calendar size={20} className="text-cyan-300" />Upcoming Events</h1>
        <p className="text-sm text-slate-400 mt-2">Published events for your campus audience.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading upcoming events…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300">Upcoming events could not be loaded.</div>
          : data.length === 0 ? <div className="card p-6 text-sm text-slate-400">No upcoming events have been published yet.</div>
            : <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{data.map(event => <EventCard key={event.id} event={event} />)}</div>}
    </section>
  );
};

const EVENT_STATUSES = ['PENDING_APPROVAL', 'APPROVED', 'PUBLISHED', 'REJECTED', 'CANCELLED'];

export const ManagementEvents: React.FC = () => {
  const queryClient = useQueryClient();
  const [renderedAt] = useState(() => new Date());
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [audienceFilter, setAudienceFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const { data = [], isLoading, isError } = useQuery<CampusEvent[]>({
    queryKey: ['management-events', statusFilter, categoryFilter, audienceFilter, fromDate, toDate],
    queryFn: async () => (await api.get('/management/events', { params: {
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
      audience: audienceFilter || undefined,
      date_from: fromDate ? `${fromDate}T00:00:00` : undefined,
      date_to: toDate ? `${toDate}T23:59:59` : undefined,
    } })).data,
  });
  const [actionError, setActionError] = useState('');
  const counts = [
    { status: 'Pending Proposals', count: data.filter(event => event.status === 'PENDING_APPROVAL').length },
    { status: 'Approved', count: data.filter(event => event.status === 'APPROVED').length },
    { status: 'Published', count: data.filter(event => event.status === 'PUBLISHED').length },
    { status: 'Rejected', count: data.filter(event => event.status === 'REJECTED').length },
    { status: 'Upcoming', count: data.filter(event => event.status === 'PUBLISHED' && new Date(event.start_dt) >= renderedAt).length },
  ];

  async function decide(event: CampusEvent, action: 'approve' | 'publish' | 'cancel' | 'reject') {
    let reason: string | undefined;
    if (action === 'reject') {
      reason = window.prompt('Reason for rejecting this proposal:')?.trim();
      if (!reason) return;
      if (reason.length < 3) {
        setActionError('Provide a rejection reason of at least three characters.');
        return;
      }
    }
    if (action === 'cancel') {
      reason = window.prompt('Cancellation reason (optional):')?.trim() || undefined;
    }
    try {
      setActionError('');
      await api.post(`/management/events/${event.id}/${action}`, action === 'reject'
        ? { reason }
        : action === 'cancel' ? { reason } : {});
      await queryClient.invalidateQueries({ queryKey: ['management-events'] });
      await queryClient.invalidateQueries({ queryKey: ['events'] });
      await queryClient.invalidateQueries({ queryKey: ['faculty-event-proposals'] });
      await queryClient.invalidateQueries({ queryKey: ['notifications'] });
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setActionError(detail || 'The event decision could not be saved.');
    }
  }

  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Calendar size={20} className="text-indigo-300" />Event Management</h1>
        <p className="text-sm text-slate-400 mt-2">Review proposals, approve events, then publish them to their selected audience.</p>
      </header>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {counts.map(({ status, count }) => <article key={status} className="stat-card">
          <p className="text-xs text-slate-400">{status.replaceAll('_', ' ')}</p>
          <p className="text-2xl font-bold text-white">{count}</p>
        </article>)}
      </div>
      <div className="card grid sm:grid-cols-2 lg:grid-cols-5 gap-3 p-4">
        <label className="text-xs text-slate-400">Status<select className="input-field mt-1" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option>{EVENT_STATUSES.map(status => <option key={status}>{status}</option>)}</select></label>
        <label className="text-xs text-slate-400">Category<select className="input-field mt-1" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="">All categories</option>{EVENT_CATEGORIES.map(([category, label]) => <option key={category} value={category}>{label}</option>)}</select></label>
        <label className="text-xs text-slate-400">Audience<select className="input-field mt-1" value={audienceFilter} onChange={event => setAudienceFilter(event.target.value)}><option value="">All audiences</option><option value="STUDENTS">Students</option><option value="FACULTY">Faculty</option><option value="STUDENTS_AND_FACULTY">Students + Faculty</option></select></label>
        <label className="text-xs text-slate-400">From date<input type="date" className="input-field mt-1" value={fromDate} onChange={event => setFromDate(event.target.value)} /></label>
        <label className="text-xs text-slate-400">To date<input type="date" className="input-field mt-1" value={toDate} onChange={event => setToDate(event.target.value)} /></label>
      </div>
      {actionError && <p role="alert" className="card p-4 text-sm text-red-300">{actionError}</p>}
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading events…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300">Events could not be loaded.</div>
          : data.length === 0 ? <div className="card p-6 text-sm text-slate-400">No events match these filters.</div>
            : <div className="space-y-4">{data.map(event => <article key={event.id} className="card p-5">
              <div className="flex flex-col lg:flex-row lg:justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold text-white">{event.title}</h2><span className="badge-amber">{event.status}</span><span className="badge-blue">{formatEventAudience(event.audience)}</span></div>
                  <p className="text-sm text-cyan-200">{formatEventCategory(event.category)} · {event.organizer || 'Organizer not listed'}{event.created_by_name ? ` · ${event.created_by_name}` : ''}</p>
                  <p className="text-sm text-slate-300">{new Date(event.start_dt).toLocaleString()} – {new Date(event.end_dt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} · {event.location || 'Venue not listed'}</p>
                  <p className="text-sm text-slate-400">{event.description}</p>
                  {event.created_at && <p className="text-xs text-slate-500">Submitted {new Date(event.created_at).toLocaleString()}</p>}
                  {event.notes && <p className="text-xs text-slate-400">Faculty notes: {event.notes}</p>}
                  {event.decision_reason && <p className="text-sm text-red-300">Decision: {event.decision_reason}</p>}
                  <Link to={`/events/${event.id}`} className="text-xs text-indigo-300 hover:text-indigo-200">View event details</Link>
                </div>
                <div className="flex flex-wrap content-start gap-2">
                  {event.status === 'PENDING_APPROVAL' && <>
                    <button className="btn-secondary" onClick={() => void decide(event, 'approve')}>Approve</button>
                    <button className="btn-secondary text-red-300" onClick={() => void decide(event, 'reject')}>Reject</button>
                  </>}
                  {event.status === 'APPROVED' && <button className="btn-primary" onClick={() => void decide(event, 'publish')}>Publish</button>}
                  {['PENDING_APPROVAL', 'APPROVED', 'PUBLISHED'].includes(event.status) && <button className="btn-secondary text-red-300" onClick={() => void decide(event, 'cancel')}>Cancel</button>}
                </div>
              </div>
            </article>)}</div>}
    </section>
  );
};

export const EventDetail: React.FC = () => {
  const { eventId } = useParams();
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<CampusEvent>({
    queryKey: ['event', eventId, user?.id],
    queryFn: async () => (await api.get(`/events/${eventId}`)).data,
    enabled: Boolean(eventId && user?.id),
  });
  if (isLoading) return <section className="card p-5 text-sm text-slate-400">Loading event…</section>;
  if (isError || !data) return <section role="alert" className="card p-5 text-sm text-red-300">This event could not be loaded or is not available to your account.</section>;
  return (
    <article className="card max-w-3xl p-6 space-y-4">
      <p className="text-xs uppercase text-cyan-300">{formatEventCategory(data.category)} · {data.status}</p>
      <h1 className="text-2xl font-bold text-white">{data.title}</h1>
      <p className="text-slate-300 whitespace-pre-wrap">{data.description}</p>
      <p className="flex items-center gap-2 text-sm text-slate-300"><Calendar size={16} />{new Date(data.start_dt).toLocaleString()} – {new Date(data.end_dt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>
      <p className="flex items-center gap-2 text-sm text-slate-300"><MapPin size={16} />{data.location || 'Venue not listed'}</p>
      <p className="flex items-center gap-2 text-sm text-slate-300"><UserRound size={16} />{data.organizer || 'Organizer not listed'} · {formatEventAudience(data.audience)}</p>
      {data.created_by_name && <p className="text-xs text-slate-500">Proposed by {data.created_by_name}</p>}
      {data.decision_reason && <p className="text-sm text-amber-200">Management decision: {data.decision_reason}</p>}
      {data.notes && user?.role !== 'STUDENT' && <p className="text-xs text-slate-400">Proposal notes: {data.notes}</p>}
      {user?.role === 'MANAGEMENT' && data.decided_at && <p className="text-xs text-slate-500">Decision recorded {new Date(data.decided_at).toLocaleString()} by {data.decided_by}</p>}
      <Link to={user?.role === 'STUDENT' ? '/student/events' : user?.role === 'FACULTY' ? '/faculty/events' : '/management/events'} className="text-sm text-indigo-300">Back to events</Link>
    </article>
  );
};

import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertCircle, BookOpen, Calendar, Users } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { formatTime, localDateString } from './facultyTypes';
import type { FacultySection, FacultySubject, FacultyTimetableEntry } from './facultyTypes';
import type { CampusEvent } from '../events/eventTypes';
import { EVENT_CATEGORIES, formatEventAudience, formatEventCategory } from '../events/eventTypes';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function TeachingError() {
  return <div role="alert" className="card p-5 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Teaching information could not be loaded.</div>;
}

function assignmentStatusLabel(status: FacultySubject['assignment_status']): string {
  switch (status) {
    case 'PENDING': return 'Pending management approval';
    case 'APPROVED': return 'Approved · awaiting assignment';
    case 'ASSIGNED': return 'Draft · awaiting publication';
    case 'PUBLISHED': return 'Published teaching assignment';
  }
}

export const FacultySubjects: React.FC = () => {
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<FacultySubject[]>({
    queryKey: ['faculty-subjects', user?.id],
    queryFn: async () => (await api.get('/faculty/subjects')).data,
    enabled: Boolean(user?.id),
  });
  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><BookOpen size={20} className="text-cyan-300" />My Subjects</h1>
        <p className="text-sm text-slate-400 mt-2">Published assignments and approved requests awaiting publication are shown separately.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading assigned subjects…</div>
        : isError ? <TeachingError />
          : !data?.length ? <div className="card p-6 text-sm text-slate-400">No subjects are currently assigned to your faculty account.</div>
            : <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.map(subject => (
                <article key={subject.id} className="card p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="text-xs font-semibold text-cyan-300">{subject.code}</p><h2 className="text-lg font-semibold text-white mt-1">{subject.name}</h2></div>
                    {subject.demo_data && <span className="badge-amber">DEMO DATA</span>}
                  </div>
                  <p className="text-sm text-slate-400 mt-3">{subject.kind || 'Class type not specified'}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className={subject.assignment_status === 'PUBLISHED' ? 'badge-green' : 'badge-amber'}>{assignmentStatusLabel(subject.assignment_status)}</span>
                    <span className="text-xs text-slate-400">{subject.weekly_periods} periods · {subject.weekly_hours.toFixed(2)} {subject.assignment_status === 'PUBLISHED' ? 'published' : 'requested'} hours/week</span>
                  </div>
                  <div className="mt-4">
                    <p className="text-xs uppercase text-slate-500">{subject.assignment_status === 'PUBLISHED' ? 'Sections taught' : 'Requested / staged sections'}</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {subject.sections.length
                        ? subject.sections.map(section => <span key={section} className="badge-blue">{section}</span>)
                        : <span className="text-xs text-slate-500">Not assigned</span>}
                    </div>
                  </div>
                  {subject.semesters.length > 0 && <p className="text-xs text-slate-500 mt-3">Semester {subject.semesters.join(', ')}</p>}
                </article>
              ))}
            </div>}
    </section>
  );
};

export const FacultySections: React.FC = () => {
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<FacultySection[]>({
    queryKey: ['faculty-sections', user?.id],
    queryFn: async () => (await api.get('/faculty/sections')).data,
    enabled: Boolean(user?.id),
  });
  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Users size={20} className="text-cyan-300" />My Sections</h1>
        <p className="text-sm text-slate-400 mt-2">Only sections in your timetable teaching assignments appear here.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading assigned sections…</div>
        : isError ? <TeachingError />
          : !data?.length ? <div className="card p-6 text-sm text-slate-400">No sections are currently assigned to your faculty account.</div>
            : <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.map(section => (
                <article key={section.id} className="card p-5">
                  <div className="flex justify-between gap-3">
                    <div><h2 className="text-lg font-semibold text-white">{section.code}</h2><p className="text-sm text-slate-400 mt-1">{section.name}</p></div>
                    {section.demo_data && <span className="badge-amber h-fit">DEMO DATA</span>}
                  </div>
                  <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                    <p><span className="block text-xs text-slate-500">Department</span>{section.department || 'Not on record'}</p>
                    <p><span className="block text-xs text-slate-500">Academic year</span>{section.year}</p>
                    <p><span className="block text-xs text-slate-500">Section strength</span>{section.strength}</p>
                  </div>
                  <div className="mt-4"><p className="text-xs uppercase text-slate-500">Your subjects</p><p className="text-sm text-cyan-200 mt-2">{section.subjects.join(', ') || 'No subjects recorded'}</p></div>
                </article>
              ))}
            </div>}
    </section>
  );
};

export const FacultyTimetable: React.FC = () => {
  const { user } = useAuth();
  const { data = [], isLoading, isError } = useQuery<FacultyTimetableEntry[]>({
    queryKey: ['faculty-week-timetable', user?.id],
    queryFn: async () => (await api.get('/faculty/timetable')).data,
    enabled: Boolean(user?.id),
  });
  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Calendar size={20} className="text-cyan-300" />My Teaching Timetable</h1>
        <p className="text-sm text-slate-400 mt-2">Published recurring weekly assignments only. Draft assignments are not displayed.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading your timetable…</div>
        : isError ? <TeachingError />
          : <div className="grid xl:grid-cols-2 gap-4">
            {WEEKDAYS.map((day, index) => {
              const entries = data.filter(entry => entry.weekday === index)
                .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
              return (
                <section key={day} className="card p-5">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3">{day}</h2>
                  {entries.length === 0 ? <p className="text-sm text-slate-500 py-2">No classes listed.</p>
                    : <div className="space-y-2">
                      {entries.map(entry => (
                        <article key={entry.id} className="rounded-lg border border-slate-800 bg-slate-800/40 p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="font-semibold text-white">{entry.subject_name || 'Scheduled class'}</p>
                              <p className="text-xs text-cyan-200 mt-1">{entry.subject_code || 'Code unavailable'} · {entry.section_code || 'Section unavailable'}</p>
                              <p className="text-xs text-slate-500 mt-1">Faculty: {entry.faculty_name || user?.full_name || 'You'}</p>
                              {entry.is_extra_class && <span className="badge-green mt-2">APPROVED EXTRA CLASS</span>}
                              <p className="text-xs text-slate-400 mt-1">{formatTime(entry.start_time)} – {formatTime(entry.end_time)} · {entry.kind}</p>
                            </div>
                            <p className="text-sm text-slate-200">{entry.effective_room_code || 'Room not assigned'}</p>
                          </div>
                          {entry.room_changed && <p className="text-xs text-amber-300 mt-2">Room changed from {entry.base_room_code || 'previous room'}{entry.change_reason ? ` · ${entry.change_reason}` : ''}</p>}
                          {entry.is_synthetic && <span className="badge-amber mt-3">DEMO DATA</span>}
                        </article>
                      ))}
                    </div>}
                </section>
              );
            })}
          </div>}
    </section>
  );
};

export const FacultyEvents: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [defaultEventDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return localDateString(tomorrow);
  });
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('WORKSHOP');
  const [description, setDescription] = useState('');
  const [eventDate, setEventDate] = useState(defaultEventDate);
  const [startTime, setStartTime] = useState('10:00');
  const [endTime, setEndTime] = useState('11:00');
  const [location, setLocation] = useState('');
  const [organizer, setOrganizer] = useState('');
  const [audience, setAudience] = useState('STUDENTS');
  const [notes, setNotes] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const { data: events = [], isLoading, isError } = useQuery<CampusEvent[]>({
    queryKey: ['events', user?.id],
    queryFn: async () => (await api.get('/events')).data,
    enabled: Boolean(user?.id),
  });
  const proposals = useQuery<CampusEvent[]>({
    queryKey: ['faculty-event-proposals', user?.id],
    queryFn: async () => (await api.get('/faculty/events/proposals')).data,
    enabled: Boolean(user?.id),
  });
  const propose = useMutation({
    mutationFn: async () => (await api.post('/faculty/events', {
      title, category, description,
      start_dt: `${eventDate}T${startTime}`,
      end_dt: `${eventDate}T${endTime}`,
      location, organizer, audience, notes: notes || null,
    })).data,
    onSuccess: () => {
      setMessage('Submitted for management approval.');
      setError('');
      setTitle('');
      setDescription('');
      setLocation('');
      setNotes('');
      queryClient.invalidateQueries({ queryKey: ['faculty-event-proposals', user?.id] });
    },
    onError: (mutationError: any) => {
      setMessage('');
      setError(mutationError.response?.data?.detail || 'The event proposal could not be submitted.');
    },
  });

  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Calendar size={20} className="text-cyan-300" />Upcoming Events</h1>
        <p className="text-sm text-slate-400 mt-2">Published events relevant to faculty, plus your private event proposals.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading published events…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300">Upcoming events could not be loaded.</div>
          : !events.length ? <div className="card p-6 text-sm text-slate-400">No upcoming events have been published for faculty.</div>
            : <div className="grid md:grid-cols-2 gap-4">{events.map(event => (
              <Link to={`/events/${event.id}`} key={event.id} className="card block p-5 hover:border-indigo-700/60 transition-colors">
                <p className="text-xs uppercase text-cyan-300">{formatEventCategory(event.category)}</p>
                <h2 className="text-lg font-semibold text-white mt-1">{event.title}</h2>
                <p className="text-sm text-slate-300 mt-3">{event.description}</p>
                <p className="text-xs text-slate-400 mt-4">{new Date(event.start_dt).toLocaleString()} – {new Date(event.end_dt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</p>
                <p className="text-xs text-slate-400 mt-2">{event.location || 'Venue not listed'} · {event.organizer || 'Organizer not listed'} · {formatEventAudience(event.audience)}</p>
              </Link>
            ))}</div>}
      <div className="card p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white">Propose Event</h2>
        <p className="text-xs text-slate-400">Management must approve and publish your proposal before it appears to its intended audience.</p>
        {message && <p role="status" className="text-sm text-emerald-300">{message}</p>}
        {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        <form className="grid md:grid-cols-2 gap-4" onSubmit={event => { event.preventDefault(); propose.mutate(); }}>
          <label className="text-xs text-slate-400">Event title<input required maxLength={200} className="input-field mt-1" value={title} onChange={event => setTitle(event.target.value)} /></label>
          <label className="text-xs text-slate-400">Category<select className="input-field mt-1" value={category} onChange={event => setCategory(event.target.value)}>{EVENT_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="text-xs text-slate-400">Date<input required type="date" className="input-field mt-1" value={eventDate} onChange={event => setEventDate(event.target.value)} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-slate-400">Start time<input required type="time" className="input-field mt-1" value={startTime} onChange={event => setStartTime(event.target.value)} /></label>
            <label className="text-xs text-slate-400">End time<input required type="time" className="input-field mt-1" value={endTime} onChange={event => setEndTime(event.target.value)} /></label>
          </div>
          <label className="text-xs text-slate-400">Venue / location<input required maxLength={250} className="input-field mt-1" value={location} onChange={event => setLocation(event.target.value)} /></label>
          <label className="text-xs text-slate-400">Organizer<input required maxLength={200} className="input-field mt-1" value={organizer} onChange={event => setOrganizer(event.target.value)} /></label>
          <label className="text-xs text-slate-400">Intended audience<select className="input-field mt-1" value={audience} onChange={event => setAudience(event.target.value)}><option value="STUDENTS">Students</option><option value="FACULTY">Faculty</option><option value="STUDENTS_AND_FACULTY">Students + Faculty</option></select></label>
          <label className="text-xs text-slate-400 md:col-span-2">Description<textarea required maxLength={4000} rows={3} className="input-field mt-1" value={description} onChange={event => setDescription(event.target.value)} /></label>
          <label className="text-xs text-slate-400 md:col-span-2">Additional notes for management<textarea maxLength={2000} rows={2} className="input-field mt-1" value={notes} onChange={event => setNotes(event.target.value)} /></label>
          <button type="submit" disabled={propose.isPending} className="btn-primary md:col-span-2">{propose.isPending ? 'Submitting…' : 'Submit for management approval'}</button>
        </form>
      </div>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-white">My Event Proposals</h2>
        {proposals.isLoading ? <p className="card p-5 text-sm text-slate-400">Loading your proposals…</p>
          : proposals.isError ? <p role="alert" className="card p-5 text-sm text-red-300">Your event proposals could not be loaded.</p>
            : !proposals.data?.length ? <p className="card p-5 text-sm text-slate-400">You have not proposed any events.</p>
              : <div className="space-y-3">{proposals.data.map(proposal => (
                <article key={proposal.id} className="card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    {proposal.status === 'PUBLISHED' && proposal.audience === 'STUDENTS'
                      ? <span className="font-semibold text-white">{proposal.title}</span>
                      : <Link to={`/events/${proposal.id}`} className="font-semibold text-white hover:text-indigo-200">{proposal.title}</Link>}
                    <span className={proposal.status === 'REJECTED' ? 'badge-red' : proposal.status === 'PUBLISHED' ? 'badge-green' : 'badge-amber'}>{proposal.status}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-2">{formatEventCategory(proposal.category)} · Submitted {proposal.created_at ? new Date(proposal.created_at).toLocaleString() : 'date unavailable'} · {new Date(proposal.start_dt).toLocaleString()}</p>
                  {proposal.decision_reason && <p className="text-sm text-amber-200 mt-2">Management decision: {proposal.decision_reason}</p>}
                </article>
              ))}</div>}
      </section>
    </section>
  );
};

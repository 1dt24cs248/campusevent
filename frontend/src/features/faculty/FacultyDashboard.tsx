import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight, Bell, BookOpen, Calendar, Clock, MapPin, Navigation,
  ShieldAlert, Siren, Utensils, Wrench,
} from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  entryEnd, entryStart,
  formatTime, localDateString, localMinutes,
} from './facultyTypes';
import type { ClassroomRequest, FacultyTimetableEntry } from './facultyTypes';

interface NotificationItem {
  id: string;
  title: string;
  body?: string | null;
  read: boolean;
}

const weekdayToday = () => (new Date().getDay() + 6) % 7;

export const FacultyDashboard: React.FC = () => {
  const { user } = useAuth();
  const [now] = useState(() => new Date());
  const today = weekdayToday();
  const nowMinutes = localMinutes(now);
  const { data: timetable = [], isLoading, isError } = useQuery<FacultyTimetableEntry[]>({
    queryKey: ['faculty-timetable', user?.id],
    queryFn: async () => (await api.get('/faculty/timetable', {
      params: { date: localDateString(new Date()) },
    })).data,
    enabled: Boolean(user?.id),
  });
  const { data: requests = [] } = useQuery<ClassroomRequest[]>({
    queryKey: ['faculty-extra-classes', user?.id],
    queryFn: async () => (await api.get('/faculty/extra-classes')).data,
    enabled: Boolean(user?.id),
  });
  const { data: notifications = [] } = useQuery<NotificationItem[]>({
    queryKey: ['notifications', user?.id],
    queryFn: async () => (await api.get('/notifications')).data,
    enabled: Boolean(user?.id),
  });
  const todayClasses = timetable
    .filter(entry => entry.weekday === today)
    .sort((a, b) => (entryStart(a) ?? 0) - (entryStart(b) ?? 0));
  const nextClass = todayClasses.find(entry => {
    const end = entryEnd(entry);
    return end !== null && end > nowMinutes;
  });
  const nextStart = nextClass ? entryStart(nextClass) : null;
  const nextLabel = nextClass && nextStart !== null
    ? nextStart <= nowMinutes ? 'In progress' : `Starts in ${nextStart - nowMinutes} min`
    : 'No more classes today';
  const changedClasses = todayClasses.filter(entry => entry.room_changed);
  const fullName = user?.full_name || user?.email || 'Faculty member';

  return (
    <div className="space-y-6">
      <header className="card p-6 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5 border-cyan-900/50">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Faculty teaching portal</p>
          <h1 className="text-2xl font-bold text-white mt-2">Good morning, {fullName}</h1>
          <p className="text-sm text-slate-300 mt-2">
            {[user?.employee_id, user?.department, user?.designation].filter(Boolean).join(' · ') || 'Faculty profile details are not fully provisioned'}
          </p>
          <p className="text-xs text-slate-500 mt-2">{new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(now)}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link to="/faculty/timetable" className="btn-secondary inline-flex items-center gap-2"><Calendar size={15} /> Teaching timetable</Link>
          <Link to="/navigator" className="btn-secondary inline-flex items-center gap-2"><Navigation size={15} /> Campus Navigator</Link>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-header"><Clock size={18} className="text-cyan-300" />Next class</h2>
            <Link to="/faculty/timetable" className="text-xs text-cyan-300 hover:text-cyan-200">Full timetable</Link>
          </div>
          {isLoading ? <p className="text-sm text-slate-400">Loading your teaching schedule…</p>
            : isError ? <p role="alert" className="text-sm text-red-300">Your teaching schedule could not be loaded.</p>
              : !nextClass ? <p className="text-sm text-slate-300 py-4">No more classes today.</p>
                : <article className="rounded-xl bg-slate-800/70 p-5">
                  <div className="flex flex-wrap justify-between gap-2">
                    <div>
                      <p className="text-lg font-semibold text-white">{nextClass.subject_name || 'Scheduled class'}</p>
                      <p className="text-sm text-cyan-200 mt-1">{nextClass.subject_code || 'Subject code unavailable'} · {nextClass.section_code || 'Section unavailable'}</p>
                      {nextClass.is_extra_class && <span className="badge-green mt-2">APPROVED EXTRA CLASS</span>}
                    </div>
                    <span className="badge-blue h-fit">{nextLabel}</span>
                  </div>
                  <div className="grid sm:grid-cols-3 gap-3 mt-5 text-sm">
                    <p><span className="text-slate-500 block text-xs">Time</span><span className="text-slate-200">{formatTime(nextClass.start_time)} – {formatTime(nextClass.end_time)}</span></p>
                    <p><span className="text-slate-500 block text-xs">Classroom</span><span className="text-slate-200">{nextClass.effective_room_code || 'Room not assigned'}</span></p>
                    <p><span className="text-slate-500 block text-xs">Class type</span><span className="text-slate-200">{nextClass.kind}</span></p>
                  </div>
                </article>}
        </section>
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
          <div className="stat-card">
            <div className="stat-icon bg-cyan-800"><Calendar size={19} className="text-cyan-100" /></div>
            <div><p className="text-xs text-slate-500">Teaching sessions today</p><p className="text-2xl font-bold text-white">{isLoading ? '—' : todayClasses.length}</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon bg-amber-800"><MapPin size={19} className="text-amber-100" /></div>
            <div><p className="text-xs text-slate-500">Room changes today</p><p className="text-2xl font-bold text-white">{isLoading ? '—' : changedClasses.length}</p></div>
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <section className="card p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-header"><BookOpen size={18} className="text-cyan-300" />Today’s teaching</h2>
            <Link to="/faculty/timetable" className="text-xs text-cyan-300">View week</Link>
          </div>
          {isLoading ? <p className="text-sm text-slate-400">Loading classes…</p>
            : isError ? <p role="alert" className="text-sm text-red-300">Classes could not be loaded.</p>
              : todayClasses.length === 0 ? <p className="text-sm text-slate-400 py-5">No classes listed for today.</p>
                : <div className="space-y-2">
                  {todayClasses.map(entry => (
                    <article key={entry.id} className="rounded-lg border border-slate-800 bg-slate-800/40 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-white">{entry.subject_name || 'Scheduled class'}</p>
                        <p className="text-xs text-slate-400 mt-1">{entry.subject_code} · {entry.section_code} · {entry.kind}{entry.is_extra_class ? ' · APPROVED EXTRA CLASS' : ''}{entry.is_synthetic ? ' · DEMO DATA' : ''}</p>
                        <p className="text-xs text-slate-500 mt-1">Faculty: {entry.faculty_name || fullName}</p>
                        <p className="text-xs text-slate-500 mt-1">{formatTime(entry.start_time)} – {formatTime(entry.end_time)}</p>
                      </div>
                      <div className="sm:text-right">
                        <p className="text-sm text-cyan-200"><MapPin size={14} className="inline mr-1" />{entry.effective_room_code || 'Room not assigned'}</p>
                        {entry.room_changed && <p className="text-xs text-amber-300 mt-1">Changed from {entry.base_room_code || 'previous room'}{entry.change_reason ? ` · ${entry.change_reason}` : ''}</p>}
                      </div>
                    </article>
                  ))}
                </div>}
        </section>
        <section className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="section-header"><Bell size={17} className="text-amber-300" />Notifications</h2>
            <Link to="/notifications" aria-label="View faculty notifications" className="text-cyan-300"><ArrowRight size={16} /></Link>
          </div>
          {notifications.length === 0 ? <p className="text-sm text-slate-500 py-4">No faculty notifications yet.</p>
            : <div className="space-y-3">{notifications.slice(0, 4).map(item => (
              <article key={item.id} className="border-b border-slate-800 pb-3 last:border-0">
                <p className="text-sm text-slate-200">{item.title}</p>
                {item.body && <p className="text-xs text-slate-400 mt-1">{item.body}</p>}
                <p className={`text-[11px] mt-1 ${item.read ? 'text-slate-600' : 'text-cyan-300'}`}>{item.read ? 'Read' : 'Unread'}</p>
              </article>
            ))}</div>}
        </section>
      </div>

      {requests.length > 0 && (
        <section className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="section-header"><Calendar size={17} className="text-emerald-300" />Approved extra classes</h2>
            <Link to="/faculty/classroom-requests" className="text-xs text-cyan-300">Manage requests</Link>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {requests.map(item => (
              <article key={item.id} className="rounded-lg border border-emerald-800/60 bg-emerald-950/20 p-4">
                <p className="font-medium text-white">{item.subject_code} · {item.section_code}</p>
                <p className="text-sm text-slate-300 mt-1">{item.requested_date} · {formatTime(item.start_time)} – {formatTime(item.end_time)}</p>
                <p className="text-sm text-emerald-200 mt-1">Room {item.approved_room_code || 'not assigned'}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Faculty campus services</h2>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Link to="/report?type=EMERGENCY" className="card p-4 hover:border-red-700/60"><Siren size={18} className="text-red-300 mb-2" /><p className="text-sm font-semibold text-white">Emergency / SOS</p></Link>
          <Link to="/report?type=SAFETY" className="card p-4 hover:border-amber-700/60"><ShieldAlert size={18} className="text-amber-300 mb-2" /><p className="text-sm font-semibold text-white">Report a safety concern</p></Link>
          <Link to="/report?type=MAINTENANCE" className="card p-4 hover:border-indigo-700/60"><Wrench size={18} className="text-indigo-300 mb-2" /><p className="text-sm font-semibold text-white">Report a campus issue</p></Link>
          <Link to="/food" className="card p-4 hover:border-emerald-700/60"><Utensils size={18} className="text-emerald-300 mb-2" /><p className="text-sm font-semibold text-white">Campus Food</p></Link>
          <Link to="/reports" className="card p-4 hover:border-cyan-700/60"><BookOpen size={18} className="text-cyan-300 mb-2" /><p className="text-sm font-semibold text-white">My campus reports</p></Link>
        </div>
      </section>
    </div>
  );
};

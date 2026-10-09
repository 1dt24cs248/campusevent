import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle, ArrowRight, Bell, BookOpen, Calendar, Clock, FileText,
  MapPin, Navigation, ShieldAlert, Siren, Utensils, Wrench,
} from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  formatTimeRange, localDateString, sortTimetable, timeMinutes, WEEKDAYS,
} from './studentTypes';
import type { StudentProfileData, StudentTimetableEntry } from './studentTypes';

interface StudentNotification {
  id: string;
  title: string;
  body?: string | null;
  read: boolean;
}

function greeting(hour: number): string {
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function timeUntil(start: number, now: number): string {
  const minutes = Math.max(0, start - now);
  if (minutes < 1) return 'Starting now';
  if (minutes < 60) return `Starts in ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `Starts in ${hours}h${remainingMinutes ? ` ${remainingMinutes}m` : ''}`;
}

export const StudentDashboard: React.FC = () => {
  const { user } = useAuth();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const today = localDateString(now);
  const { data: profile, isLoading: profileLoading, isError: profileError } = useQuery<StudentProfileData>({
    queryKey: ['student-profile', user?.id],
    queryFn: async () => (await api.get('/student/profile')).data,
    enabled: Boolean(user?.id),
  });
  const { data: timetable = [], isLoading: timetableLoading, isError: timetableError } = useQuery<StudentTimetableEntry[]>({
    queryKey: ['student-timetable', user?.id, today],
    queryFn: async () => (await api.get('/timetable/me', { params: { date: today } })).data,
    enabled: Boolean(user?.id),
  });
  const { data: notifications = [], isLoading: notificationsLoading, isError: notificationsError } = useQuery<StudentNotification[]>({
    queryKey: ['notifications', user?.id],
    queryFn: async () => (await api.get('/notifications')).data,
    enabled: Boolean(user?.id),
  });

  const weekday = (now.getDay() + 6) % 7;
  const todaysSchedule = sortTimetable(timetable.filter(entry => entry.weekday === weekday));
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nextClass = todaysSchedule.find(entry => {
    const end = timeMinutes(entry.end_time);
    const start = timeMinutes(entry.start_time);
    return end !== null ? end > nowMinutes : start === null || start >= nowMinutes;
  });
  const nextStart = timeMinutes(nextClass?.start_time);
  const nextEnd = timeMinutes(nextClass?.end_time);
  const classInProgress = nextClass !== undefined
    && nextStart !== null
    && nextEnd !== null
    && nextStart <= nowMinutes
    && nowMinutes < nextEnd;
  const classroomChanges = todaysSchedule.filter(entry => entry.room_changed);
  const displayName = profile?.full_name || user?.full_name || user?.email || 'Student';
  const academicSummary = [
    profile?.program,
    profile?.department,
    profile?.semester ? `Semester ${profile.semester}` : null,
    profile?.section,
  ].filter(Boolean).join(' · ');

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Student portal</p>
          <h1 className="text-2xl font-bold text-white mt-1">{greeting(now.getHours())}, {displayName}</h1>
          <p className="text-sm text-slate-400 mt-1">{new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(now)}</p>
          {profileLoading ? <p className="text-sm text-slate-500 mt-2">Loading your academic identity…</p> : (
            <p className="text-sm text-slate-300 mt-2">
              {[profile?.usn || user?.usn, ...academicSummary.split(' · ')].filter(Boolean).join(' · ') || 'Academic profile details are not provisioned.'}
            </p>
          )}
          {profileError && <p role="alert" className="text-xs text-red-300 mt-2">Your student profile could not be loaded.</p>}
        </div>
        <Link to="/student/timetable" className="btn-secondary flex items-center justify-center gap-2">
          <Calendar size={16} /> My Timetable
        </Link>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h2 className="section-header"><Clock size={18} className="text-cyan-400" />Next class</h2>
            <Link to="/student/timetable" className="text-xs text-indigo-300 hover:text-indigo-200">Full timetable</Link>
          </div>
          {timetableLoading ? <p className="text-sm text-slate-500">Loading your section schedule…</p>
            : timetableError ? <p role="alert" className="text-sm text-red-300">Your timetable could not be loaded.</p>
              : !nextClass ? <div className="rounded-lg bg-slate-800/50 p-5 text-sm text-slate-300">No more classes today.</div>
                : (
                  <article className="rounded-xl border border-indigo-800/60 bg-indigo-950/30 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-lg font-semibold text-white">{nextClass.subject_name || 'Scheduled class'}</p>
                      {nextClass.is_extra_class && <span className="badge-green">APPROVED EXTRA CLASS</span>}
                      <span className="badge-blue">{classInProgress ? 'In progress' : nextStart === null ? 'Time not published' : timeUntil(nextStart, nowMinutes)}</span>
                    </div>
                    <p className="text-sm text-indigo-200 mt-1">{nextClass.subject_code || 'Subject code not listed'}</p>
                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                      <div><p className="text-xs text-slate-500">Time</p><p className="text-slate-200 mt-1">{formatTimeRange(nextClass)}</p></div>
                      <div><p className="text-xs text-slate-500">Faculty</p><p className="text-slate-200 mt-1">{nextClass.faculty_name || 'Not listed'}</p></div>
                      <div><p className="text-xs text-slate-500">Classroom</p><p className="text-slate-200 mt-1">{nextClass.effective_room_code || 'Not assigned'}</p></div>
                    </div>
                  </article>
                )}
        </section>
        <section className="grid grid-cols-2 lg:grid-cols-1 gap-4">
          <div className="stat-card">
            <div className="stat-icon bg-indigo-700"><Calendar size={19} className="text-white" /></div>
            <div><p className="text-xs text-slate-500">Classes today</p><p className="text-2xl font-bold text-white">{timetableLoading ? '—' : todaysSchedule.length}</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon bg-amber-700"><MapPin size={19} className="text-white" /></div>
            <div><p className="text-xs text-slate-500">Classroom changes today</p><p className="text-2xl font-bold text-white">{timetableLoading ? '—' : classroomChanges.length}</p></div>
          </div>
        </section>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Today’s classes</h2>
          <Link to="/student/timetable" className="text-xs text-indigo-300 hover:text-indigo-200">View week</Link>
        </div>
        {timetableLoading ? <div className="card p-5 text-sm text-slate-500">Loading your timetable…</div>
          : timetableError ? <div role="alert" className="card p-5 text-sm text-red-300">Today’s classes could not be loaded.</div>
            : todaysSchedule.length === 0 ? <div className="card p-5 text-sm text-slate-400">No classes listed for {WEEKDAYS[weekday] || 'today'}.</div>
              : <div className="space-y-2">
                {todaysSchedule.map(entry => (
                  <article key={entry.id} className={`card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${entry.room_changed ? 'border-amber-700/60' : ''}`}>
                    <div className="min-w-0">
                      <p className="font-semibold text-white">{entry.subject_name || 'Scheduled class'}</p>
                      {entry.is_extra_class && <span className="badge-green">APPROVED EXTRA CLASS</span>}
                      <p className="text-xs text-slate-400 mt-1">
                        {entry.subject_code || 'Code not listed'} · {entry.faculty_name || 'Faculty not listed'}
                        {entry.is_synthetic && <span className="ml-2 badge-amber">DEMO DATA</span>}
                      </p>
                    </div>
                    <div className="text-sm text-slate-300 sm:text-right">
                      <p>{formatTimeRange(entry)}</p>
                      <p className="text-xs text-slate-500 mt-1">Room: {entry.effective_room_code || 'Not assigned'}</p>
                    </div>
                    {entry.room_changed && (
                      <p className="text-xs text-amber-200 sm:max-w-52">
                        Classroom changed: {entry.base_room_code || 'Unassigned'} → {entry.effective_room_code || 'Unassigned'}
                        {entry.change_reason ? ` · ${entry.change_reason}` : ''}
                      </p>
                    )}
                  </article>
                ))}
              </div>}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Campus services</h2>
          <Link to="/reports" className="text-xs text-indigo-300 hover:text-indigo-200">My Reports</Link>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
          <Link to="/report?type=EMERGENCY" className="rounded-xl border border-red-700/50 bg-red-950/30 p-4 hover:bg-red-900/30 transition-colors">
            <Siren size={19} className="text-red-300 mb-2" /><p className="text-sm font-semibold text-red-100">Emergency / SOS</p>
          </Link>
          <Link to="/report?type=SAFETY" className="card p-4 hover:border-amber-700/60 transition-colors">
            <ShieldAlert size={19} className="text-amber-300 mb-2" /><p className="text-sm font-semibold text-white">Safety concern</p>
          </Link>
          <Link to="/report?type=MAINTENANCE" className="card p-4 hover:border-indigo-700/60 transition-colors">
            <Wrench size={19} className="text-indigo-300 mb-2" /><p className="text-sm font-semibold text-white">Report an issue</p>
          </Link>
          <Link to="/food" className="card p-4 hover:border-emerald-700/60 transition-colors">
            <Utensils size={19} className="text-emerald-300 mb-2" /><p className="text-sm font-semibold text-white">Campus Food</p>
          </Link>
          <Link to="/reports" className="card p-4 hover:border-cyan-700/60 transition-colors">
            <FileText size={19} className="text-cyan-300 mb-2" /><p className="text-sm font-semibold text-white">My Reports</p>
          </Link>
          <Link to="/student/events" className="card p-4 hover:border-indigo-700/60 transition-colors">
            <Calendar size={19} className="text-indigo-300 mb-2" /><p className="text-sm font-semibold text-white">Upcoming Events</p>
          </Link>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <section className="card p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-header"><Bell size={18} className="text-amber-400" />Notifications</h2>
            <Link to="/notifications" aria-label="View all notifications" className="text-indigo-300"><ArrowRight size={16} /></Link>
          </div>
          {notificationsLoading ? <p className="text-sm text-slate-500">Loading notifications…</p>
            : notificationsError ? <p role="alert" className="text-sm text-red-300">Notifications could not be loaded.</p>
              : notifications.length === 0 ? <p className="text-sm text-slate-500 py-5 text-center">No notifications yet.</p>
                : <div className="space-y-3">
                  {notifications.slice(0, 5).map(notification => (
                    <article key={notification.id} className="border-b border-slate-800 pb-3 last:border-0">
                      <p className="text-sm font-medium text-slate-200">{notification.title}</p>
                      {notification.body && <p className="text-xs text-slate-400 mt-1 line-clamp-2">{notification.body}</p>}
                      <p className={`text-[11px] mt-1 ${notification.read ? 'text-slate-600' : 'text-cyan-400'}`}>{notification.read ? 'Read' : 'Unread'}</p>
                    </article>
                  ))}
                </div>}
        </section>
        <div className="space-y-3">
          <Link to="/navigator" className="card p-4 flex items-center gap-3 hover:border-cyan-700 transition-colors">
            <Navigation size={18} className="text-cyan-300" /><span className="text-sm font-semibold text-white">Campus Navigator</span><ArrowRight size={15} className="ml-auto text-slate-500" />
          </Link>
          <Link to="/ai" className="card p-4 flex items-center gap-3 hover:border-indigo-700 transition-colors">
            <AlertCircle size={18} className="text-indigo-300" /><span className="text-sm font-semibold text-white">Campus AI</span><ArrowRight size={15} className="ml-auto text-slate-500" />
          </Link>
          <Link to="/student/academics" className="card p-4 flex items-center gap-3 hover:border-indigo-700 transition-colors">
            <BookOpen size={18} className="text-indigo-300" /><span className="text-sm font-semibold text-white">My Academics</span><ArrowRight size={15} className="ml-auto text-slate-500" />
          </Link>
        </div>
      </div>
    </div>
  );
};

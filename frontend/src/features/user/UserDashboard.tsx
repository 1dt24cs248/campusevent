import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  AlertCircle, ArrowRight, Bell, BookOpen, Calendar, Clock, MapPin, Navigation,
  FileText, ShieldAlert, Siren, Utensils, Wrench,
} from 'lucide-react';

interface TimetableEntry {
  id: string;
  section_code?: string | null;
  subject_name?: string | null;
  faculty_name?: string | null;
  weekday: number;
  start_slot: string;
  duration_slots: number;
  base_room_code?: string | null;
  effective_room_code?: string | null;
  room_changed: boolean;
  change_reason?: string | null;
}

interface Notification {
  id: string;
  title: string;
  body?: string | null;
  created_at?: string | null;
  read: boolean;
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const PERIODS: Record<string, [number, number]> = {
  P1: [9 * 60 + 30, 10 * 60 + 25],
  P2: [10 * 60 + 25, 11 * 60 + 20],
  P3: [11 * 60 + 35, 12 * 60 + 30],
  P4: [12 * 60 + 30, 13 * 60 + 25],
  P5: [14 * 60 + 15, 15 * 60 + 10],
  P6: [15 * 60 + 10, 16 * 60 + 5],
  P7: [16 * 60 + 5, 17 * 60],
};

function slotMinutes(slot: string): number | null {
  const match = slot.match(/^(\d{1,2}):(\d{2})$/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : PERIODS[slot]?.[0] ?? null;
}

function formatSlot(slot: string): string {
  const period = PERIODS[slot];
  if (!period) return slot;
  const formatTime = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
  return `${formatTime(period[0])}–${formatTime(period[1])}`;
}

function localDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function todayEntries(entries: TimetableEntry[], now: Date): TimetableEntry[] {
  const today = (now.getDay() + 6) % 7;
  return entries
    .filter(entry => entry.weekday === today)
    .sort((a, b) => a.start_slot.localeCompare(b.start_slot));
}

export const UserDashboard: React.FC<{ role: 'STUDENT' | 'FACULTY' }> = ({ role }) => {
  const { user } = useAuth();
  const [now] = useState(() => new Date());
  const { data: timetable = [], isLoading: timetableLoading, isError: timetableError } = useQuery<TimetableEntry[]>({
    queryKey: ['timetable-me', user?.id],
    queryFn: async () => (await api.get('/timetable/me', {
      params: { date: localDateString(new Date()) },
    })).data,
  });
  const { data: notifications = [], isLoading: notificationsLoading, isError: notificationsError } = useQuery<Notification[]>({
    queryKey: ['notifications', user?.id],
    queryFn: async () => (await api.get('/notifications')).data,
  });

  const todaysSchedule = todayEntries(timetable, now);
  const nextClass = todaysSchedule.find(entry => {
    const start = slotMinutes(entry.start_slot);
    return start === null || start >= now.getHours() * 60 + now.getMinutes();
  });
  const changedClasses = todaysSchedule.filter(entry => entry.room_changed);
  const heading = role === 'STUDENT' ? 'Student dashboard' : 'Faculty dashboard';
  const scheduleLabel = role === 'STUDENT' ? 'Today’s classes' : 'Today’s teaching schedule';

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Campus Intelligence</p>
          <h1 className="text-2xl font-bold text-white mt-1">{heading}</h1>
          <p className="text-sm text-slate-400 mt-1">{new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(now)}</p>
          <p className="text-sm text-slate-300 mt-2">
            {user?.full_name || user?.email}
            {role === 'STUDENT'
              ? ` · ${user?.usn || 'USN not provisioned'} · ${[user?.department, user?.program, user?.semester ? `Semester ${user.semester}` : null, user?.section].filter(Boolean).join(' · ') || 'Academic profile not provisioned'}`
              : ` · ${user?.employee_id || 'Employee ID not provisioned'} · ${[user?.department, user?.designation].filter(Boolean).join(' · ') || 'Faculty profile not provisioned'}`}
          </p>
        </div>
        <Link to="/navigator" className="btn-secondary flex items-center justify-center gap-2">
          <Navigation size={16} /> Campus Navigator
        </Link>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="stat-card">
          <div className="stat-icon bg-indigo-700"><Calendar size={19} className="text-white" /></div>
          <div><p className="text-xs text-slate-500">Classes today</p><p className="text-2xl font-bold text-white">{timetableLoading ? '—' : todaysSchedule.length}</p></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon bg-cyan-700"><Clock size={19} className="text-white" /></div>
          <div><p className="text-xs text-slate-500">Next class</p><p className="text-sm font-semibold text-white mt-1">{timetableLoading ? 'Loading…' : nextClass?.subject_name || 'No more classes today'}</p></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon bg-amber-700"><Bell size={19} className="text-white" /></div>
          <div><p className="text-xs text-slate-500">Room changes today</p><p className="text-2xl font-bold text-white">{timetableLoading ? '—' : changedClasses.length}</p></div>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Quick campus actions</h2>
          <Link to="/reports" className="text-xs text-indigo-300 hover:text-indigo-200">My Reports</Link>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <Link to="/report?type=EMERGENCY" className="rounded-xl border border-red-700/50 bg-red-950/30 p-4 hover:bg-red-900/30 transition-colors">
            <Siren size={19} className="text-red-300 mb-2" />
            <p className="text-sm font-semibold text-red-100">Emergency / SOS</p>
            <p className="text-[11px] text-red-300/70 mt-1">Requires a final confirmation</p>
          </Link>
          <Link to="/report?type=SAFETY" className="card p-4 hover:border-amber-700/60 transition-colors">
            <ShieldAlert size={19} className="text-amber-300 mb-2" />
            <p className="text-sm font-semibold text-white">Safety concern</p>
          </Link>
          <Link to="/report?type=MAINTENANCE" className="card p-4 hover:border-indigo-700/60 transition-colors">
            <Wrench size={19} className="text-indigo-300 mb-2" />
            <p className="text-sm font-semibold text-white">Report an issue</p>
          </Link>
          <Link to="/food" className="card p-4 hover:border-emerald-700/60 transition-colors">
            <Utensils size={19} className="text-emerald-300 mb-2" />
            <p className="text-sm font-semibold text-white">Campus Food</p>
          </Link>
          <Link to="/reports" className="card p-4 hover:border-cyan-700/60 transition-colors">
            <FileText size={19} className="text-cyan-300 mb-2" />
            <p className="text-sm font-semibold text-white">My Reports</p>
          </Link>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <section className="card p-5 xl:col-span-2">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h2 className="section-header"><BookOpen size={18} className="text-indigo-400" />{scheduleLabel}</h2>
            <Link to="/navigator" className="text-xs text-indigo-300 hover:text-indigo-200 flex items-center gap-1">
              Find a room <ArrowRight size={13} />
            </Link>
          </div>
          {timetableLoading ? (
            <div className="space-y-3 animate-pulse">{[1, 2, 3].map(item => <div key={item} className="h-16 rounded-lg bg-slate-800" />)}</div>
          ) : timetableError ? (
            <div role="alert" className="flex items-center gap-2 text-sm text-red-300 p-4 rounded-lg bg-red-900/20">
              <AlertCircle size={16} /> Schedule could not be loaded. Please try again.
            </div>
          ) : todaysSchedule.length === 0 ? (
            <div className="text-center py-10">
              <Calendar size={24} className="text-slate-600 mx-auto mb-2" />
              <p className="text-sm text-slate-300">No classes listed for {WEEKDAYS[(now.getDay() + 6) % 7]}.</p>
              <p className="text-xs text-slate-500 mt-1">Your timetable is loaded from the campus schedule.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {todaysSchedule.map(entry => (
                <article key={entry.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-800/40 p-4">
                  <div className="min-w-0">
                    <p className="font-semibold text-white">{entry.subject_name || 'Scheduled class'}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {[formatSlot(entry.start_slot), entry.section_code, role === 'STUDENT' ? entry.faculty_name : null].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <div className="sm:text-right flex-shrink-0">
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-cyan-300 sm:justify-end">
                      <MapPin size={14} />{entry.effective_room_code || 'Room not assigned'}
                    </p>
                    {entry.room_changed && (
                      <p className="text-xs text-amber-300 mt-1">
                        Changed from {entry.base_room_code || 'previous room'}
                        {entry.change_reason ? ` · ${entry.change_reason}` : ''}
                      </p>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-header"><Bell size={18} className="text-amber-400" />Notifications</h2>
            <Link to="/notifications" aria-label="View all notifications" className="text-indigo-300"><ArrowRight size={16} /></Link>
          </div>
          {notificationsLoading ? <p className="text-sm text-slate-500">Loading notifications…</p>
            : notificationsError ? <p role="alert" className="text-sm text-red-300">Notifications could not be loaded.</p>
              : notifications.length === 0 ? <p className="text-sm text-slate-500 py-6 text-center">No notifications yet.</p>
                : <div className="space-y-3">
                  {notifications.slice(0, 5).map(notification => (
                    <article key={notification.id} className="border-b border-slate-800 pb-3 last:border-0">
                      <p className="text-sm font-medium text-slate-200">{notification.title}</p>
                      {notification.body && <p className="text-xs text-slate-400 mt-1 line-clamp-2">{notification.body}</p>}
                      <p className={`text-[11px] mt-1 ${notification.read ? 'text-slate-600' : 'text-cyan-400'}`}>
                        {notification.read ? 'Read' : 'Unread'}
                      </p>
                    </article>
                  ))}
                  <Link to="/notifications" className="text-xs text-indigo-300 hover:text-indigo-200">View all notifications</Link>
                </div>}
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Link to="/navigator" className="card p-5 hover:border-cyan-700 transition-colors">
          <div className="flex items-center gap-3">
            <div className="stat-icon bg-cyan-900"><MapPin size={18} className="text-cyan-300" /></div>
            <div><p className="font-semibold text-white">Campus Navigator</p><p className="text-xs text-slate-400 mt-1">Find a classroom and view its campus route.</p></div>
            <ArrowRight size={16} className="ml-auto text-slate-500" />
          </div>
        </Link>
        <Link to="/ai" className="card p-5 hover:border-indigo-700 transition-colors">
          <div className="flex items-center gap-3">
            <div className="stat-icon bg-indigo-900"><AlertCircle size={18} className="text-indigo-300" /></div>
            <div><p className="font-semibold text-white">Campus AI</p><p className="text-xs text-slate-400 mt-1">Ask about your schedule, room changes, or a scenario.</p></div>
            <ArrowRight size={16} className="ml-auto text-slate-500" />
          </div>
        </Link>
      </div>
    </div>
  );
};

import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Calendar, MapPin } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  formatTimeRange, localDateString, sortTimetable, WEEKDAYS,
} from './studentTypes';
import type { StudentTimetableEntry } from './studentTypes';

export const StudentTimetable: React.FC = () => {
  const { user } = useAuth();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const date = localDateString(now);
  const { data: entries = [], isLoading, isError } = useQuery<StudentTimetableEntry[]>({
    queryKey: ['student-timetable', user?.id, date],
    queryFn: async () => (await api.get('/timetable/me', { params: { date } })).data,
    enabled: Boolean(user?.id),
  });

  return (
    <section className="max-w-5xl space-y-5">
      <header>
        <h1 className="section-header"><Calendar size={20} className="text-cyan-300" />My Timetable</h1>
        <p className="text-sm text-slate-400 mt-2">Your weekly classes come from your linked section. Active room/time changes for today are applied where available.</p>
      </header>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading your section timetable…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Your timetable could not be loaded.</div>
          : (
            <div className="space-y-5">
              {WEEKDAYS.map((weekday, index) => {
                const dayEntries = sortTimetable(entries.filter(entry => entry.weekday === index));
                return (
                  <section key={weekday} className="card p-5">
                    <h2 className="font-semibold text-white">{weekday}</h2>
                    {!dayEntries.length ? <p className="text-sm text-slate-500 mt-3">No classes listed.</p>
                      : <div className="space-y-2 mt-3">
                        {dayEntries.map(entry => (
                          <article key={entry.id} className={`rounded-lg border bg-slate-900/60 p-4 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 ${entry.room_changed ? 'border-amber-700/60' : 'border-slate-800'}`}>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-medium text-white">{entry.subject_name || 'Scheduled class'}</h3>
                                {entry.is_extra_class && <span className="badge-green">APPROVED EXTRA CLASS</span>}
                                {entry.is_synthetic && <span className="badge-amber">DEMO DATA</span>}
                              </div>
                              <p className="text-xs text-slate-400 mt-1">{entry.subject_code || 'Code not listed'} · {entry.faculty_name || 'Faculty not listed'}</p>
                              {entry.room_changed && (
                                <p className="text-xs text-amber-200 mt-2">
                                  Classroom changed: {entry.base_room_code || 'Unassigned'} → {entry.effective_room_code || 'Unassigned'}
                                  {entry.change_reason ? ` · ${entry.change_reason}` : ''}
                                </p>
                              )}
                            </div>
                            <div className="text-sm text-slate-300 md:text-right">
                              <p>{formatTimeRange(entry)}</p>
                              <p className="text-xs text-slate-500 mt-1 inline-flex md:justify-end items-center gap-1"><MapPin size={12} />{entry.effective_room_code || 'Room not assigned'}</p>
                            </div>
                          </article>
                        ))}
                      </div>}
                  </section>
                );
              })}
            </div>
          )}
    </section>
  );
};

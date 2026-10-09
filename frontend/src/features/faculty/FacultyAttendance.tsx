import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ClipboardCheck } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { formatTime, localDateString } from './facultyTypes';
import type { FacultyTimetableEntry } from './facultyTypes';

interface AttendanceSession {
  id: string;
  timetable_entry_id: string;
  session_date: string;
  start_time: string;
  status: string;
  section_code: string;
  subject_code: string;
  subject_name: string;
  records_entered: number;
}

interface AttendanceRoster {
  id: string;
  section_code: string;
  subject_code: string;
  subject_name: string;
  session_date: string;
  status: string;
  records: { student_id: string; usn?: string | null; name: string; status?: 'PRESENT' | 'ABSENT' | null }[];
}

export const FacultyAttendance: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [today] = useState(() => new Date());
  const todayString = localDateString(today);
  const [entryId, setEntryId] = useState('');
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [marksBySession, setMarksBySession] = useState<Record<string, Record<string, 'PRESENT' | 'ABSENT' | ''>>>({});
  const [error, setError] = useState('');
  const { data: timetable = [], isLoading: timetableLoading } = useQuery<FacultyTimetableEntry[]>({
    queryKey: ['faculty-timetable', user?.id],
    queryFn: async () => (await api.get('/faculty/timetable', { params: { date: todayString } })).data,
    enabled: Boolean(user?.id),
  });
  const { data: sessions = [], isLoading: sessionsLoading, isError } = useQuery<AttendanceSession[]>({
    queryKey: ['faculty-attendance', user?.id],
    queryFn: async () => (await api.get('/faculty/attendance')).data,
    enabled: Boolean(user?.id),
  });
  const todaysClasses = timetable.filter(entry => entry.weekday === (today.getDay() + 6) % 7);
  const { data: selectedSession, isLoading: rosterLoading, isError: rosterError } = useQuery<AttendanceRoster>({
    queryKey: ['faculty-attendance-roster', user?.id, selectedSessionId],
    queryFn: async () => (await api.get(`/faculty/attendance/${encodeURIComponent(selectedSessionId)}`)).data,
    enabled: Boolean(user?.id && selectedSessionId),
  });
  const marks = useMemo(() => Object.fromEntries((selectedSession?.records || []).map(record => [
    record.student_id,
    marksBySession[selectedSessionId]?.[record.student_id] ?? record.status ?? '',
  ])), [selectedSession, selectedSessionId, marksBySession]);
  const startSession = useMutation({
    mutationFn: async () => (await api.post('/faculty/attendance', {
      timetable_entry_id: entryId,
      session_date: todayString,
    })).data,
    onSuccess: (created: AttendanceSession) => {
      setError('');
      queryClient.invalidateQueries({ queryKey: ['faculty-attendance', user?.id] });
      setSelectedSessionId(created.id);
    },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Attendance session could not be started.'),
  });
  const saveMarks = useMutation({
    mutationFn: async () => (await api.put(`/faculty/attendance/${encodeURIComponent(selectedSessionId)}/records`, {
      records: Object.entries(marks).map(([student_id, status]) => ({ student_id, status })),
    })).data,
    onSuccess: () => {
      setError('');
      queryClient.invalidateQueries({ queryKey: ['faculty-attendance', user?.id] });
      queryClient.invalidateQueries({ queryKey: ['faculty-attendance-roster', user?.id, selectedSessionId] });
    },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Attendance could not be saved.'),
  });
  const sessionEntryIds = new Set(sessions.filter(session => session.session_date === todayString).map(session => session.timetable_entry_id));
  const allMarked = selectedSession
    ? selectedSession.records.length > 0
      && selectedSession.records.every(record => marks[record.student_id] === 'PRESENT' || marks[record.student_id] === 'ABSENT')
    : false;

  return (
    <section className="max-w-5xl space-y-5">
      <header>
        <h1 className="section-header"><ClipboardCheck size={20} className="text-cyan-300" />Attendance</h1>
        <p className="text-sm text-slate-400 mt-2">Open a scheduled class assigned to you, mark its roster, and save the session.</p>
      </header>
      <div className="card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-200">Start Attendance</h2>
        <label className="block text-xs text-slate-400">
          Select section, subject, and scheduled class
          <select className="input-field mt-2" value={entryId} onChange={event => { setEntryId(event.target.value); setError(''); }}>
            <option value="">Choose today’s teaching session</option>
            {todaysClasses.map(entry => (
              <option key={entry.id} value={entry.id} disabled={sessionEntryIds.has(entry.id)}>
                {entry.section_code} · {entry.subject_code} {entry.subject_name} · {formatTime(entry.start_time)}{sessionEntryIds.has(entry.id) ? ' · Attendance started' : ''}
              </option>
            ))}
          </select>
        </label>
        {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        <button className="btn-primary" disabled={!entryId || sessionEntryIds.has(entryId) || startSession.isPending || timetableLoading} onClick={() => startSession.mutate()}>
          {startSession.isPending ? 'Starting…' : sessionEntryIds.has(entryId) ? 'Attendance started' : 'Start Attendance'}
        </button>
        {!timetableLoading && todaysClasses.length === 0 && <p className="text-sm text-slate-500">No scheduled classes are assigned to you today.</p>}
      </div>
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">Attendance sessions</h2>
        {sessionsLoading ? <p className="text-sm text-slate-400">Loading sessions…</p>
          : isError ? <p role="alert" className="text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Attendance sessions could not be loaded.</p>
            : sessions.length === 0 ? <p className="text-sm text-slate-400">Attendance records have not been entered yet.</p>
              : <div className="space-y-3">{sessions.map(session => (
                <article key={session.id} className={`rounded-lg border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${selectedSessionId === session.id ? 'border-cyan-700' : 'border-slate-800'}`}>
                  <div><p className="font-medium text-white">{session.subject_code} · {session.section_code}</p><p className="text-xs text-slate-400 mt-1">{session.session_date} · {formatTime(session.start_time)} · {session.status}</p></div>
                  <div className="flex items-center gap-3"><p className="text-xs text-slate-400">{session.records_entered === 0 ? 'Attendance records have not been entered yet.' : `${session.records_entered} attendance records`}</p><button className="btn-secondary" onClick={() => setSelectedSessionId(session.id)}>Open roster</button></div>
                </article>
              ))}</div>}
      </div>
      {selectedSessionId && (
        <div className="card p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold text-slate-200">Mark attendance</h2><p className="text-xs text-slate-400 mt-1">{selectedSession?.subject_code} · {selectedSession?.section_code} · {selectedSession?.session_date}</p></div>
            <div className="flex gap-2">
              <button className="btn-secondary" disabled={!selectedSession?.records.length} onClick={() => setMarksBySession(previous => ({
                ...previous,
                [selectedSessionId]: Object.fromEntries((selectedSession?.records || []).map(row => [row.student_id, 'PRESENT'])),
              }))}>Select all present</button>
              <button className="btn-primary" disabled={!allMarked || saveMarks.isPending || !selectedSession?.records.length} onClick={() => { if (window.confirm('Save attendance for every student in this section?')) saveMarks.mutate(); }}>
                {saveMarks.isPending ? 'Saving…' : 'Save attendance'}
              </button>
            </div>
          </div>
          {rosterLoading ? <p className="text-sm text-slate-400">Loading section roster…</p>
            : rosterError ? <p role="alert" className="text-sm text-red-300">The attendance roster could not be loaded.</p>
              : !selectedSession?.records.length ? <p className="text-sm text-slate-400">No students are assigned to this section.</p>
                : <div className="divide-y divide-slate-800">{selectedSession.records.map(record => (
                  <div key={record.student_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div><p className="text-sm text-slate-200">{record.name}</p><p className="text-xs text-slate-500">{record.usn || 'USN not assigned'}</p></div>
                    <div className="flex gap-2">
                      {(['PRESENT', 'ABSENT'] as const).map(value => <button key={value} aria-pressed={marks[record.student_id] === value} className={`rounded-lg border px-3 py-1.5 text-xs ${marks[record.student_id] === value ? (value === 'PRESENT' ? 'border-emerald-600 bg-emerald-950 text-emerald-200' : 'border-red-700 bg-red-950 text-red-200') : 'border-slate-700 text-slate-400'}`} onClick={() => setMarksBySession(previous => ({
                        ...previous,
                        [selectedSessionId]: { ...previous[selectedSessionId], [record.student_id]: value },
                      }))}>{value}</button>)}
                    </div>
                  </div>
                ))}</div>}
          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        </div>
      )}
    </section>
  );
};

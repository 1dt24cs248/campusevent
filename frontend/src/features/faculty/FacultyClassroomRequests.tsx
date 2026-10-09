import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Building2, Clock } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { formatTime, localDateString } from './facultyTypes';
import type { ClassroomRequest, FacultySection, FacultyTimetableEntry } from './facultyTypes';

interface ClassroomOptions {
  floors: Array<{ id: string; name: string; level: number }>;
  rooms: Array<{ id: string; code: string; floor_id: string; capacity: number | null }>;
}

const statusClass: Record<ClassroomRequest['status'], string> = {
  PENDING: 'badge-amber',
  APPROVED: 'badge-green',
  REJECTED: 'badge-red',
  CANCELLED: 'badge-blue',
};

export const FacultyClassroomRequests: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [today] = useState(() => localDateString(new Date()));
  const [assignmentKey, setAssignmentKey] = useState('');
  const [requestedDate, setRequestedDate] = useState(today);
  const [startTime, setStartTime] = useState('17:00');
  const [endTime, setEndTime] = useState('17:30');
  const [strength, setStrength] = useState('1');
  const [floorId, setFloorId] = useState('');
  const [roomId, setRoomId] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const { data: timetable = [] } = useQuery<FacultyTimetableEntry[]>({
    queryKey: ['faculty-week-timetable', user?.id],
    queryFn: async () => (await api.get('/faculty/timetable', { params: { date: today } })).data,
    enabled: Boolean(user?.id),
  });
  const { data: sections = [] } = useQuery<FacultySection[]>({
    queryKey: ['faculty-sections', user?.id],
    queryFn: async () => (await api.get('/faculty/sections')).data,
    enabled: Boolean(user?.id),
  });
  const { data: options } = useQuery<ClassroomOptions>({
    queryKey: ['faculty-classroom-options'],
    queryFn: async () => (await api.get('/faculty/classroom-options')).data,
    enabled: Boolean(user?.id),
  });
  const { data: requests = [], isLoading, isError } = useQuery<ClassroomRequest[]>({
    queryKey: ['faculty-classroom-requests', user?.id],
    queryFn: async () => (await api.get('/faculty/classroom-requests')).data,
    enabled: Boolean(user?.id),
  });

  const assignments = useMemo(() => {
    const seen = new Set<string>();
    return timetable.flatMap(entry => {
      if (!entry.subject_id || !entry.section_id) return [];
      const key = `${entry.subject_id}:${entry.section_id}`;
      if (seen.has(key)) return [];
      seen.add(key);
      return [{
        key,
        subject_id: entry.subject_id,
        subject_code: entry.subject_code || 'Subject',
        subject_name: entry.subject_name || '',
        section_id: entry.section_id,
        section_code: entry.section_code || 'Section',
      }];
    });
  }, [timetable]);
  const selectedAssignment = assignments.find(assignment => assignment.key === assignmentKey);
  const selectedSection = sections.find(section => section.id === selectedAssignment?.section_id);
  const visibleRooms = options?.rooms.filter(room => !floorId || room.floor_id === floorId) || [];

  const createRequest = useMutation({
    mutationFn: async () => (await api.post('/faculty/classroom-requests', {
      subject_id: selectedAssignment?.subject_id,
      section_id: selectedAssignment?.section_id,
      requested_date: requestedDate,
      start_time: startTime,
      end_time: endTime,
      expected_strength: Number(strength),
      preferred_floor_id: floorId || null,
      preferred_room_id: roomId || null,
      reason,
    })).data,
    onSuccess: () => {
      setError('');
      setReason('');
      queryClient.invalidateQueries({ queryKey: ['faculty-classroom-requests', user?.id] });
      queryClient.invalidateQueries({ queryKey: ['faculty-extra-classes', user?.id] });
    },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Your classroom request could not be submitted.'),
  });
  const cancelRequest = useMutation({
    mutationFn: async (requestId: string) => api.post(`/faculty/classroom-requests/${requestId}/cancel`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['faculty-classroom-requests', user?.id] }),
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'The request could not be cancelled.'),
  });

  return (
    <section className="max-w-6xl space-y-5">
      <header>
        <h1 className="section-header"><Building2 size={20} className="text-cyan-300" />Classroom Requests</h1>
        <p className="text-sm text-slate-400 mt-2">Request an additional room for a subject and section you are assigned to teach. Management confirms availability before approval.</p>
      </header>
      <form className="card p-5 grid md:grid-cols-2 xl:grid-cols-3 gap-4" onSubmit={event => { event.preventDefault(); createRequest.mutate(); }}>
        <label className="text-xs text-slate-400 md:col-span-2 xl:col-span-3">
          Subject and section
          <select required className="input-field mt-2" value={assignmentKey} onChange={event => {
            const value = event.target.value;
            const assignment = assignments.find(item => item.key === value);
            setAssignmentKey(value);
            setStrength(String(sections.find(section => section.id === assignment?.section_id)?.strength || 1));
            setFloorId('');
            setRoomId('');
          }}>
            <option value="">Select one of your teaching assignments</option>
            {assignments.map(assignment => <option key={assignment.key} value={assignment.key}>{assignment.subject_code} {assignment.subject_name} · {assignment.section_code}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-400">Date<input className="input-field mt-2" required type="date" min={today} value={requestedDate} onChange={event => setRequestedDate(event.target.value)} /></label>
        <label className="text-xs text-slate-400">Start time<input className="input-field mt-2" required type="time" value={startTime} onChange={event => setStartTime(event.target.value)} /></label>
        <label className="text-xs text-slate-400">End time<input className="input-field mt-2" required type="time" value={endTime} onChange={event => setEndTime(event.target.value)} /></label>
        <label className="text-xs text-slate-400">Expected student strength<input className="input-field mt-2" required type="number" min="1" max={selectedSection?.strength || 1000} value={strength} onChange={event => setStrength(event.target.value)} /></label>
        <label className="text-xs text-slate-400">Preferred floor (optional)
          <select className="input-field mt-2" value={floorId} onChange={event => { setFloorId(event.target.value); setRoomId(''); }}>
            <option value="">No preference</option>
            {options?.floors.map(floor => <option key={floor.id} value={floor.id}>{floor.name} · Level {floor.level}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-400">Preferred room (optional)
          <select className="input-field mt-2" value={roomId} onChange={event => setRoomId(event.target.value)}>
            <option value="">No preference</option>
            {visibleRooms.map(room => <option key={room.id} value={room.id}>{room.code}{room.capacity !== null ? ` · capacity ${room.capacity}` : ''}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-400 md:col-span-2 xl:col-span-3">Reason
          <textarea className="input-field mt-2 min-h-24" required minLength={5} maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} placeholder="Explain the need for this additional classroom." />
        </label>
        {error && <p role="alert" className="md:col-span-2 xl:col-span-3 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />{error}</p>}
        <div className="md:col-span-2 xl:col-span-3"><button className="btn-primary" disabled={!assignmentKey || createRequest.isPending}>{createRequest.isPending ? 'Submitting…' : 'Submit classroom request'}</button></div>
      </form>
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">My requests</h2>
        {isLoading ? <p className="text-sm text-slate-400">Loading your requests…</p>
          : isError ? <p role="alert" className="text-sm text-red-300">Your requests could not be loaded.</p>
            : requests.length === 0 ? <p className="text-sm text-slate-400">You have not submitted a classroom request.</p>
              : <div className="space-y-3">{requests.map(request => (
                <article key={request.id} className="rounded-lg border border-slate-800 p-4">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{request.subject_code} · {request.section_code}</p>
                      <p className="text-sm text-slate-300 mt-1"><Clock size={14} className="inline mr-1" />{request.requested_date} · {formatTime(request.start_time)} – {formatTime(request.end_time)}</p>
                      <p className="text-xs text-slate-400 mt-2">{request.reason}</p>
                      {request.status === 'APPROVED' && <p className="text-sm text-emerald-200 mt-2">Confirmed room: {request.approved_room_code}</p>}
                      {request.status === 'REJECTED' && <p className="text-sm text-red-300 mt-2">Reason: {request.decision_reason || 'No reason recorded'}</p>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={statusClass[request.status]}>{request.status}</span>
                      {request.status === 'PENDING' && <button type="button" className="btn-secondary text-xs" disabled={cancelRequest.isPending} onClick={() => cancelRequest.mutate(request.id)}>Cancel</button>}
                    </div>
                  </div>
                </article>
              ))}</div>}
      </div>
    </section>
  );
};

import React, { useState } from 'react';
import { AxiosError } from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CalendarCheck, Check, Plus, Send, X } from 'lucide-react';
import api from '../../api/client';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const SLOTS = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'];

type Assignment = { section_id: string; room_id: string; weekday: number; start_slot: string; duration_slots: number };
type RequestItem = {
  id: string;
  subject_id: string;
  subject_code: string;
  subject_name: string;
  subject_kind: string | null;
  subject_lab_kind: string | null;
  required_facilities: string[];
  preferred_section_ids: string[];
  preferred_sections: { id: string; code: string }[];
  eligible_sections: { id: string; code: string; strength: number }[];
  availability: Record<string, string[]>;
  periods_per_week: number;
  status: string;
  decision_reason: string | null;
  assignments: (Assignment & { id: string; section_code: string; room_code: string; published: boolean })[];
};
type SubjectRequest = {
  id: string;
  faculty_id: string;
  faculty_name: string;
  department: string | null;
  designation: string | null;
  note: string | null;
  status: string;
  created_at: string;
  items: RequestItem[];
};
type ManagementRoom = { id: string; code: string; display_name: string; floor_id: string; capacity: number | null; resource_type: string; lab_kind: string | null; facilities: string[]; status: string; allocatable_for_classes: boolean };
type EligibilityData = {
  faculty: { id: string; name: string; employee_id: string | null; department: string | null }[];
  academic_years: number[];
  sections: { id: string; code: string; name: string; year: number; department: string | null }[];
  eligibility: { faculty_id: string; academic_year: number | null; section_id: string | null }[];
};

function errorText(error: unknown): string {
  if (error instanceof AxiosError && typeof error.response?.data?.detail === 'string') return error.response.data.detail;
  return 'The subject request could not be updated.';
}

function FacultyEligibility() {
  const queryClient = useQueryClient();
  const [facultyId, setFacultyId] = useState('');
  const [academicYears, setAcademicYears] = useState<number[] | null>(null);
  const [sectionIds, setSectionIds] = useState<string[] | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const eligibilityQuery = useQuery<EligibilityData>({
    queryKey: ['management-faculty-teaching-eligibility'],
    queryFn: async () => (await api.get('/management/faculty-teaching-eligibility')).data,
  });

  const selectedFacultyId = facultyId || eligibilityQuery.data?.faculty[0]?.id || '';
  const savedRows = eligibilityQuery.data?.eligibility.filter(
    row => row.faculty_id === selectedFacultyId,
  ) || [];
  const selectedAcademicYears = academicYears ?? savedRows.flatMap(
    row => row.academic_year === null ? [] : [row.academic_year],
  );
  const selectedSectionIds = sectionIds ?? savedRows.flatMap(
    row => row.section_id ? [row.section_id] : [],
  );

  const save = useMutation({
    mutationFn: async () => api.put(`/management/faculty/${selectedFacultyId}/teaching-eligibility`, {
      academic_years: selectedAcademicYears,
      section_ids: selectedSectionIds,
    }),
    onSuccess: async () => {
      setError('');
      setMessage('Teaching eligibility saved. This does not approve a subject request or assign classes.');
      setAcademicYears(null);
      setSectionIds(null);
      await queryClient.invalidateQueries({ queryKey: ['management-faculty-teaching-eligibility'] });
    },
    onError: failure => { setMessage(''); setError(errorText(failure)); },
  });

  const selectFaculty = (id: string) => {
    setFacultyId(id);
    setAcademicYears(null);
    setSectionIds(null);
    setMessage('');
  };

  return (
    <section className="card space-y-4 p-5">
      <div>
        <h2 className="font-semibold text-white">1. Teaching eligibility</h2>
        <p className="mt-1 text-sm text-slate-400">Designate academic years and/or specific sections a faculty member may request. Eligibility is separate from approval, assignment, and publication.</p>
      </div>
      {eligibilityQuery.isLoading ? <p className="text-sm text-slate-400">Loading eligibility options…</p>
        : eligibilityQuery.isError ? <p role="alert" className="text-sm text-red-300">Eligibility options could not be loaded.</p>
          : !eligibilityQuery.data?.faculty.length ? <p className="text-sm text-slate-400">No faculty profiles are available.</p>
            : <>
              <label className="block max-w-lg text-xs text-slate-400">Faculty<select className="input-field mt-1" value={selectedFacultyId} onChange={event => selectFaculty(event.target.value)}>{eligibilityQuery.data.faculty.map(faculty => <option key={faculty.id} value={faculty.id}>{faculty.name}{faculty.employee_id ? ` · ${faculty.employee_id}` : ''}{faculty.department ? ` · ${faculty.department}` : ''}</option>)}</select></label>
              <div className="grid gap-5 lg:grid-cols-2">
                <fieldset>
                  <legend className="text-xs font-medium text-slate-400">Eligible academic years</legend>
                  <div className="mt-2 flex flex-wrap gap-4">{eligibilityQuery.data.academic_years.map(year => <label key={year} className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={selectedAcademicYears.includes(year)} onChange={() => setAcademicYears(current => (current ?? selectedAcademicYears).includes(year) ? (current ?? selectedAcademicYears).filter(value => value !== year) : [...(current ?? selectedAcademicYears), year].sort((a, b) => a - b))} className="h-4 w-4 accent-indigo-500" />Year {year}</label>)}</div>
                </fieldset>
                <fieldset>
                  <legend className="text-xs font-medium text-slate-400">Additional specific sections</legend>
                  <div className="mt-2 max-h-48 space-y-2 overflow-y-auto">{eligibilityQuery.data.sections.map(section => <label key={section.id} className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={selectedSectionIds.includes(section.id)} onChange={() => setSectionIds(current => (current ?? selectedSectionIds).includes(section.id) ? (current ?? selectedSectionIds).filter(id => id !== section.id) : [...(current ?? selectedSectionIds), section.id])} className="h-4 w-4 accent-indigo-500" />{section.code} · Year {section.year}{section.department ? ` · ${section.department}` : ''}</label>)}</div>
                </fieldset>
              </div>
              {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
              {message && <p role="status" className="text-sm text-emerald-300">{message}</p>}
              <button type="button" className="btn-primary" disabled={save.isPending || !selectedFacultyId} onClick={() => { setError(''); setMessage(''); save.mutate(); }}>{save.isPending ? 'Saving…' : 'Save teaching eligibility'}</button>
            </>}
    </section>
  );
}

function AssignmentEditor({ request, item, rooms, onRefresh, setError }: {
  request: SubjectRequest;
  item: RequestItem;
  rooms: ManagementRoom[];
  onRefresh: () => void;
  setError: (value: string) => void;
}) {
  const queryClient = useQueryClient();
  const [assignments, setAssignments] = useState<Assignment[]>(() => item.assignments.length
    ? item.assignments.map(({ section_id, room_id, weekday, start_slot, duration_slots }) => ({ section_id, room_id, weekday, start_slot, duration_slots }))
    : [{ section_id: item.eligible_sections[0]?.id || '', room_id: '', weekday: 0, start_slot: 'P1', duration_slots: 1 }]);
  const [feedback, setFeedback] = useState('');
  const baseUrl = `/management/faculty-subject-requests/${request.id}/items/${item.id}`;
  const save = useMutation({
    mutationFn: async () => api.put(`${baseUrl}/assignments`, { assignments }),
    onSuccess: async () => {
      setFeedback('Assignments validated and saved as a draft. They are not visible on timetables yet.');
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['management-faculty-subject-requests'] });
      onRefresh();
    },
    onError: error => { setFeedback(''); setError(errorText(error)); },
  });
  const publish = useMutation({
    mutationFn: async () => api.post(`${baseUrl}/publish`),
    onSuccess: async () => {
      setFeedback('Weekly assignment published to faculty and section timetables.');
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['management-faculty-subject-requests'] });
      await queryClient.invalidateQueries({ queryKey: ['management-faculty'] });
      await queryClient.invalidateQueries({ queryKey: ['notifications'] });
      onRefresh();
    },
    onError: error => { setFeedback(''); setError(errorText(error)); },
  });
  const scheduledPeriods = assignments.reduce((total, assignment) => total + Number(assignment.duration_slots || 0), 0);
  const availableSlots = (weekday: number) => item.availability[(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'] as const)[weekday]];
  const slotAllowed = (assignment: Assignment) => {
    const allowed = availableSlots(assignment.weekday);
    if (!allowed) return true;
    const startIndex = SLOTS.indexOf(assignment.start_slot);
    return startIndex >= 0 && Array.from({ length: assignment.duration_slots }, (_, offset) => SLOTS[startIndex + offset]).every(slot => allowed.includes(slot));
  };
  const update = (index: number, changes: Partial<Assignment>) => setAssignments(current => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...changes } : row));

  return (
    <div className="mt-4 space-y-3 border-t border-slate-800 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-white">Weekly assignment · {scheduledPeriods}/{item.periods_per_week} periods</p>
        <button type="button" className="btn-secondary inline-flex items-center gap-2 text-xs" onClick={() => setAssignments(current => [...current, { section_id: item.eligible_sections[0]?.id || '', room_id: '', weekday: 0, start_slot: 'P1', duration_slots: 1 }])} disabled={scheduledPeriods >= item.periods_per_week}><Plus size={14} />Add period</button>
      </div>
      {assignments.map((assignment, index) => {
        const startIndex = SLOTS.indexOf(assignment.start_slot);
        const slotsFit = startIndex >= 0 && startIndex + assignment.duration_slots <= SLOTS.length;
        const capacity = item.eligible_sections.find(section => section.id === assignment.section_id)?.strength || 0;
        return (
          <div key={`${index}-${assignment.weekday}-${assignment.start_slot}`} className="grid gap-2 rounded-lg border border-slate-800 p-3 sm:grid-cols-2 xl:grid-cols-5">
            <label className="text-xs text-slate-400">Section<select className="input-field mt-1" value={assignment.section_id} onChange={event => update(index, { section_id: event.target.value })}><option value="">Choose section</option>{item.eligible_sections.map(section => <option key={section.id} value={section.id}>{section.code} · {section.strength} students</option>)}</select></label>
            <label className="text-xs text-slate-400">{(item.subject_kind || 'THEORY').toUpperCase() === 'LAB' ? 'Laboratory' : 'Classroom / seminar room'}<select className="input-field mt-1" value={assignment.room_id} onChange={event => update(index, { room_id: event.target.value })}><option value="">Choose room</option>{rooms.map(room => { const isLab = (item.subject_kind || 'THEORY').toUpperCase() === 'LAB'; const wrongLabKind = isLab && Boolean(item.subject_lab_kind) && room.lab_kind !== item.subject_lab_kind; const missingFacilities = item.required_facilities.some(facility => !room.facilities.includes(facility)); const disabled = room.status !== 'ACTIVE' || !room.allocatable_for_classes || room.capacity === null || room.capacity < capacity || (isLab ? room.resource_type !== 'LAB' || wrongLabKind : !['CLASSROOM', 'SEMINAR_HALL'].includes(room.resource_type)) || missingFacilities; return <option key={room.id} value={room.id} disabled={disabled}>{room.code} · {room.resource_type} · capacity {room.capacity ?? 'unknown'}{disabled ? ' · unavailable/ineligible' : ''}</option>; })}</select></label>
            <label className="text-xs text-slate-400">Day<select className="input-field mt-1" value={assignment.weekday} onChange={event => update(index, { weekday: Number(event.target.value) })}>{WEEKDAYS.map((day, dayIndex) => <option key={day} value={dayIndex}>{day}</option>)}</select></label>
            <label className="text-xs text-slate-400">Start period<select className="input-field mt-1" value={assignment.start_slot} onChange={event => update(index, { start_slot: event.target.value })}>{SLOTS.map(slot => <option key={slot}>{slot}</option>)}</select></label>
            <label className="text-xs text-slate-400">Periods<select className="input-field mt-1" value={assignment.duration_slots} onChange={event => update(index, { duration_slots: Number(event.target.value) })}><option value={1}>1</option><option value={2}>2</option></select></label>
            {(!slotsFit || !slotAllowed(assignment)) && <p className="sm:col-span-2 xl:col-span-5 text-xs text-amber-300">This slot exceeds the teaching day or is outside the faculty's declared availability.</p>}
            <button type="button" className="sm:col-span-2 xl:col-span-5 w-fit text-xs text-red-300" onClick={() => setAssignments(current => current.filter((_, rowIndex) => rowIndex !== index))} disabled={assignments.length === 1}>Remove period</button>
          </div>
        );
      })}
      {feedback && <p role="status" className="text-sm text-emerald-300">{feedback}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" disabled={save.isPending || scheduledPeriods !== item.periods_per_week || assignments.some(row => !row.section_id || !row.room_id || !slotAllowed(row))} onClick={() => save.mutate()}>{save.isPending ? 'Validating…' : 'Validate & save draft'}</button>
        {item.status === 'ASSIGNED' && <button type="button" className="btn-primary inline-flex items-center gap-2" disabled={publish.isPending} onClick={() => publish.mutate()}><Send size={14} />{publish.isPending ? 'Publishing…' : 'Publish timetable'}</button>}
      </div>
    </div>
  );
}

function RequestItemCard({ request, item, rooms, roomsLoading, roomsError, onChanged, setError }: {
  request: SubjectRequest;
  item: RequestItem;
  rooms: ManagementRoom[];
  roomsLoading: boolean;
  roomsError: boolean;
  onChanged: () => void;
  setError: (value: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();
  const review = useMutation({
    mutationFn: async (status: 'APPROVED' | 'REJECTED') => api.post(
      `/management/faculty-subject-requests/${request.id}/items/${item.id}/review`,
      { status, reason: reason.trim() || null },
    ),
    onSuccess: async () => {
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['management-faculty-subject-requests'] });
      await queryClient.invalidateQueries({ queryKey: ['notifications'] });
      onChanged();
    },
    onError: error => setError(errorText(error)),
  });

  return (
    <div className="border-t border-slate-800 py-4 first:border-0 first:pt-0">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-white">{item.subject_code} · {item.subject_name}</h3><span className={item.status === 'PENDING' ? 'badge-amber' : item.status === 'REJECTED' ? 'badge-red' : item.status === 'PUBLISHED' ? 'badge-green' : 'badge-blue'}>{item.status}</span></div>
          <p className="mt-1 text-xs text-slate-400">Preferred sections: {item.preferred_sections.map(section => section.code).join(', ') || 'No preference'} · {item.periods_per_week} periods/week</p>
          {Object.keys(item.availability).length > 0 && <p className="mt-1 text-xs text-slate-500">Availability: {Object.entries(item.availability).map(([day, slots]) => `${day} ${slots.join(', ')}`).join(' · ')}</p>}
          {item.decision_reason && <p className="mt-2 text-sm text-slate-400">Decision: {item.decision_reason}</p>}
          {item.assignments.map(assignment => <p key={assignment.id} className="mt-2 text-xs text-slate-300">{WEEKDAYS[assignment.weekday]} {assignment.start_slot} · {assignment.section_code} · {assignment.room_code} · {assignment.published ? 'Published' : 'Draft'}</p>)}
        </div>
        {item.status === 'PENDING' && <div className="w-full space-y-2 lg:w-80">
          <label className="block text-xs text-slate-400">Management comment or rejection reason<input className="input-field mt-1" value={reason} onChange={event => setReason(event.target.value)} maxLength={1000} placeholder="Required when rejecting" /></label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary inline-flex items-center gap-1" disabled={review.isPending} onClick={() => review.mutate('APPROVED')}><Check size={14} />Approve request</button>
            <button type="button" className="btn-secondary inline-flex items-center gap-1 text-red-300" disabled={review.isPending || reason.trim().length < 3} onClick={() => review.mutate('REJECTED')}><X size={14} />Reject</button>
          </div>
        </div>}
        {['APPROVED', 'ASSIGNED'].includes(item.status) && <button type="button" className="btn-secondary h-fit" onClick={() => setExpanded(value => !value)}>{expanded ? 'Hide assignment' : 'Assign timetable'}</button>}
      </div>
      {expanded && (roomsLoading ? <p className="mt-4 text-sm text-slate-400">Loading eligible rooms…</p>
        : roomsError ? <p role="alert" className="mt-4 text-sm text-red-300">Room options could not be loaded.</p>
          : <AssignmentEditor request={request} item={item} rooms={rooms} setError={setError} onRefresh={onChanged} />)}
    </div>
  );
}

export const FacultySubjectRequests: React.FC = () => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState('');
  const { data = [], isLoading, isError, refetch } = useQuery<SubjectRequest[]>({
    queryKey: ['management-faculty-subject-requests', statusFilter],
    queryFn: async () => (await api.get('/management/faculty-subject-requests', { params: statusFilter ? { status: statusFilter } : {} })).data,
  });
  const roomsQuery = useQuery<ManagementRoom[]>({
    queryKey: ['management-classroom-request-rooms'],
    queryFn: async () => (await api.get('/management/classroom-requests/rooms')).data,
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['management-faculty-subject-requests'] });
    void refetch();
  };

  return (
    <section className="max-w-6xl space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div><h1 className="section-header"><CalendarCheck size={20} className="text-indigo-300" />Faculty Subject Requests</h1><p className="mt-2 text-sm text-slate-400">Set teaching eligibility, review each request, then assign and publish a conflict-checked weekly timetable.</p></div>
        <label className="text-xs text-slate-400">Status<select className="input-field mt-1 min-w-48" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All requests</option><option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="ASSIGNMENT_IN_PROGRESS">Assignment in progress</option><option value="PARTIALLY_PUBLISHED">Partially published</option><option value="COMPLETED">Completed</option></select></label>
      </header>
      <FacultyEligibility />
      {error && <p role="alert" className="card flex items-center gap-2 p-4 text-sm text-red-300"><AlertCircle size={16} />{error}</p>}
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading faculty subject requests…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300">Faculty subject requests could not be loaded.</div>
          : !data.length ? <div className="card p-6 text-sm text-slate-400">No faculty subject requests match this filter.</div>
            : <div className="space-y-4">{data.map(request => <article key={request.id} className="card p-5">
              <div className="flex flex-col gap-2 border-b border-slate-800 pb-4 sm:flex-row sm:items-start sm:justify-between">
                <div><h2 className="font-semibold text-white">{request.faculty_name}</h2><p className="mt-1 text-sm text-slate-400">{request.department || 'Department not configured'} · {request.designation || 'Designation not provided'}</p>{request.note && <p className="mt-2 text-sm text-slate-300">{request.note}</p>}</div>
                <div className="sm:text-right"><span className="badge-blue">{request.status.replaceAll('_', ' ')}</span><p className="mt-2 text-xs text-slate-500">Requested {new Date(request.created_at).toLocaleString()}</p></div>
              </div>
              {request.items.map(item => <RequestItemCard key={item.id} request={request} item={item} rooms={roomsQuery.data || []} roomsLoading={roomsQuery.isLoading} roomsError={roomsQuery.isError} onChanged={refresh} setError={setError} />)}
            </article>)}</div>}
    </section>
  );
};

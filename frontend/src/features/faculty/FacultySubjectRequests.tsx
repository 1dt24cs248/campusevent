import React, { useState } from 'react';
import { AxiosError } from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, BookOpenCheck, Send } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';

const WEEKDAYS = [
  ['MON', 'Monday'], ['TUE', 'Tuesday'], ['WED', 'Wednesday'],
  ['THU', 'Thursday'], ['FRI', 'Friday'], ['SAT', 'Saturday'],
] as const;
const SLOTS = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'];

type EligibleSection = { id: string; code: string };
type EligibleSubject = {
  id: string;
  code: string;
  name: string;
  kind: string | null;
  already_assigned: boolean;
  active_request_status: string | null;
  is_synthetic: boolean;
  eligible_sections: EligibleSection[];
};
type SubjectCatalog = { department: string | null; subjects: EligibleSubject[]; message?: string };
type RequestDraft = { periods: number; sectionIds: string[]; days: string[]; slots: string[] };
type RequestItem = {
  id: string;
  subject_code: string;
  subject_name: string;
  preferred_sections: EligibleSection[];
  availability: Record<string, string[]>;
  periods_per_week: number;
  status: string;
  decision_reason: string | null;
  assignments: { id: string; section_code: string; room_code: string; weekday: number; start_slot: string; duration_slots: number; published: boolean }[];
};
type SubjectRequest = { id: string; note: string | null; status: string; created_at: string; items: RequestItem[] };
type FacultyNotification = { id: string; type: string; title: string; body: string | null; created_at: string };

function messageFromError(error: unknown): string {
  if (error instanceof AxiosError && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  return 'Subject request could not be completed.';
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter(item => item !== value) : [...values, value];
}

export const FacultySubjectRequests: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, RequestDraft>>({});
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');

  const catalogQuery = useQuery<SubjectCatalog>({
    queryKey: ['faculty-subject-catalog', user?.id],
    queryFn: async () => (await api.get('/faculty/subject-catalog')).data,
    enabled: Boolean(user?.id),
  });
  const requestsQuery = useQuery<SubjectRequest[]>({
    queryKey: ['faculty-subject-requests', user?.id],
    queryFn: async () => (await api.get('/faculty/subject-requests')).data,
    enabled: Boolean(user?.id),
  });
  const notificationsQuery = useQuery<FacultyNotification[]>({
    queryKey: ['notifications', user?.id],
    queryFn: async () => (await api.get('/notifications')).data,
    enabled: Boolean(user?.id),
  });
  const requestNotifications = (notificationsQuery.data || []).filter(notification => (
    notification.type === 'FACULTY_SUBJECT_REQUEST'
  ));
  const submitRequest = useMutation({
    mutationFn: async () => {
      const items = Object.entries(drafts).filter(([, draft]) => draft).map(([subject_id, draft]) => ({
        subject_id,
        preferred_section_ids: draft.sectionIds,
        periods_per_week: draft.periods,
        availability: Object.fromEntries(draft.days.map(day => [day, draft.slots])),
      }));
      return api.post('/faculty/subject-requests', { note: note || null, items });
    },
    onSuccess: async () => {
      setDrafts({});
      setNote('');
      setError('');
      setFeedback('Your subject request was sent to management.');
      await queryClient.invalidateQueries({ queryKey: ['faculty-subject-requests', user?.id] });
      await queryClient.invalidateQueries({ queryKey: ['notifications', user?.id] });
    },
    onError: failure => { setFeedback(''); setError(messageFromError(failure)); },
  });

  const updateDraft = (subjectId: string, update: Partial<RequestDraft>) => {
    setDrafts(current => ({
      ...current,
      [subjectId]: {
        periods: current[subjectId]?.periods ?? 1,
        sectionIds: current[subjectId]?.sectionIds ?? [],
        days: current[subjectId]?.days ?? [],
        slots: current[subjectId]?.slots ?? [],
        ...update,
      },
    }));
  };
  const selectedCount = Object.keys(drafts).length;

  return (
    <section className="max-w-5xl space-y-5">
      <header>
        <h1 className="section-header"><BookOpenCheck size={20} className="text-cyan-300" />Subject Requests</h1>
        <p className="mt-2 text-sm text-slate-400">Choose existing subjects offered to the academic years or sections management designated for you. Eligibility, approval, assignment, and timetable publication are separate steps.</p>
      </header>

      <section className="card p-5">
        <h2 className="font-semibold text-white">Faculty identity</h2>
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
          <p><span className="block text-xs text-slate-500">Name</span>{user?.display_name || user?.full_name || user?.email || 'Faculty'}</p>
          <p><span className="block text-xs text-slate-500">Department</span>{user?.department || catalogQuery.data?.department || 'Department not configured'}</p>
          <p><span className="block text-xs text-slate-500">Designation</span>{user?.designation || 'Not provided'}</p>
        </div>
        {user?.department && <p className="mt-4 text-xs text-slate-500">Current assigned subjects and weekly timetable remain available under My Subjects and Teaching Timetable.</p>}
      </section>

      {catalogQuery.isLoading ? <div className="card p-5 text-sm text-slate-400">Loading eligible subjects…</div>
        : catalogQuery.isError ? <div role="alert" className="card p-5 text-sm text-red-300">Eligible subjects could not be loaded.</div>
          : !catalogQuery.data?.subjects.length ? <div className="card p-5 text-sm text-slate-400">{catalogQuery.data?.message || 'No eligible subjects are available for your department.'}</div>
            : <>
              <div className="space-y-3">
                {catalogQuery.data.subjects.map(subject => {
                  const selected = Boolean(drafts[subject.id]);
                  const draft = drafts[subject.id];
                  return (
                    <article key={subject.id} className="card p-5 space-y-4">
                      <label className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={subject.already_assigned || Boolean(subject.active_request_status)}
                          onChange={event => {
                            setError('');
                            setFeedback('');
                            setDrafts(current => {
                              const next = { ...current };
                              if (event.target.checked) next[subject.id] = { periods: 1, sectionIds: [], days: [], slots: [] };
                              else delete next[subject.id];
                              return next;
                            });
                          }}
                          className="mt-1 h-4 w-4 accent-cyan-500"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2 font-semibold text-white">{subject.code} · {subject.name}
                            {subject.already_assigned && <span className="badge-green">Already assigned</span>}
                            {subject.active_request_status && <span className="badge-amber">Request {subject.active_request_status.toLowerCase()}</span>}
                            {subject.is_synthetic && <span className="badge-amber">Demo data</span>}
                          </span>
                          <span className="mt-1 block text-xs text-slate-500">{subject.kind || 'Teaching type not specified'} · {subject.eligible_sections.length} eligible sections</span>
                        </span>
                      </label>

                      {selected && draft && <div className="grid gap-5 border-t border-slate-800 pt-4 lg:grid-cols-2">
                        <div>
                          <p className="text-xs font-medium text-slate-400">Preferred sections</p>
                          {!subject.eligible_sections.length ? <p className="mt-2 text-xs text-amber-300">No existing subject-to-section offering is linked to your designated eligibility.</p>
                            : <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">{subject.eligible_sections.map(section => <label key={section.id} className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={draft.sectionIds.includes(section.id)} onChange={() => updateDraft(subject.id, { sectionIds: toggleValue(draft.sectionIds, section.id) })} className="h-4 w-4 accent-cyan-500" />{section.code}</label>)}</div>}
                          <label className="mt-4 block text-xs text-slate-400">Required periods per week
                            <input className="input-field mt-1 max-w-40" type="number" min="1" max="7" value={draft.periods} onChange={event => updateDraft(subject.id, { periods: Number(event.target.value) })} />
                          </label>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-slate-400">Availability (optional)</p>
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">{WEEKDAYS.map(([day, label]) => <label key={day} className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={draft.days.includes(day)} onChange={() => updateDraft(subject.id, { days: toggleValue(draft.days, day) })} className="h-4 w-4 accent-cyan-500" />{label}</label>)}</div>
                          {draft.days.length > 0 && <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">{SLOTS.map(slot => <label key={slot} className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={draft.slots.includes(slot)} onChange={() => updateDraft(subject.id, { slots: toggleValue(draft.slots, slot) })} className="h-4 w-4 accent-cyan-500" />{slot}</label>)}</div>}
                          {draft.days.length > 0 && draft.slots.length === 0 && <p className="mt-2 text-xs text-amber-300">Select at least one available period, or clear the day selections.</p>}
                        </div>
                      </div>}
                    </article>
                  );
                })}
              </div>
              <form className="card space-y-4 p-5" onSubmit={event => { event.preventDefault(); setFeedback(''); setError(''); submitRequest.mutate(); }}>
                <label className="block text-xs text-slate-400">Note for management (optional)<textarea className="input-field mt-2 min-h-24" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></label>
                {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
                {feedback && <p role="status" className="text-sm text-emerald-300">{feedback}</p>}
                <button type="submit" disabled={!selectedCount || Object.values(drafts).some(draft => draft.days.length > 0 && !draft.slots.length) || submitRequest.isPending} className="btn-primary inline-flex items-center gap-2"><Send size={15} />{submitRequest.isPending ? 'Sending…' : `Submit ${selectedCount || ''} subject${selectedCount === 1 ? '' : 's'}`}</button>
              </form>
            </>}

      <section className="space-y-3">
        <h2 className="section-header"><Bell size={18} className="text-amber-300" />Request notifications</h2>
        {notificationsQuery.isLoading ? <div className="card p-5 text-sm text-slate-400">Loading notifications…</div>
          : notificationsQuery.isError ? <div role="alert" className="card p-5 text-sm text-red-300">Notifications could not be loaded.</div>
            : !requestNotifications.length ? <div className="card p-5 text-sm text-slate-400">No subject request notifications yet.</div>
              : <div className="space-y-2">{requestNotifications.map(notification => <article key={notification.id} className="card p-4"><p className="font-medium text-white">{notification.title}</p><p className="mt-1 text-sm text-slate-300">{notification.body}</p><p className="mt-2 text-xs text-slate-500">{new Date(notification.created_at).toLocaleString()}</p></article>)}</div>}
      </section>

      <section className="space-y-3">
        <h2 className="section-header">My request history</h2>
        {requestsQuery.isLoading ? <div className="card p-5 text-sm text-slate-400">Loading request history…</div>
          : requestsQuery.isError ? <div role="alert" className="card p-5 text-sm text-red-300">Request history could not be loaded.</div>
            : !requestsQuery.data?.length ? <div className="card p-5 text-sm text-slate-400">You have not submitted any subject requests.</div>
              : requestsQuery.data.map(request => <article key={request.id} className="card p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">Submitted {new Date(request.created_at).toLocaleString()}</p><span className={request.status === 'COMPLETED' ? 'badge-green' : request.status === 'PENDING' ? 'badge-amber' : 'badge-blue'}>{request.status.replaceAll('_', ' ')}</span></div>
                {request.note && <p className="text-sm text-slate-400">{request.note}</p>}
                {request.items.map(item => <div key={item.id} className="border-t border-slate-800 pt-3">
                  <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium text-white">{item.subject_code} · {item.subject_name}</p><span className={item.status === 'PUBLISHED' ? 'badge-green' : item.status === 'REJECTED' ? 'badge-red' : item.status === 'PENDING' ? 'badge-amber' : 'badge-blue'}>{item.status}</span></div>
                  <p className="mt-1 text-xs text-slate-500">{item.periods_per_week} periods/week · Preferred sections: {item.preferred_sections.map(section => section.code).join(', ') || 'No preference'}</p>
                  {item.decision_reason && <p className="mt-2 text-sm text-slate-400">Management: {item.decision_reason}</p>}
                  {item.assignments.map(assignment => <p key={assignment.id} className="mt-2 text-sm text-slate-300">{WEEKDAYS[assignment.weekday][1]} {assignment.start_slot} · {assignment.section_code} · {assignment.room_code} {assignment.published ? '· Published' : '· Awaiting publication'}</p>)}
                </div>)}
              </article>)}
      </section>
    </section>
  );
};

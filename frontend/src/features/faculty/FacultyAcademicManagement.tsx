import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, BookOpenCheck } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';

interface AcademicAssignment {
  subject_id: string;
  subject_code: string;
  subject_name: string;
  section_id: string;
  section_code: string;
  is_synthetic: boolean;
}

interface AcademicContent {
  assessments: { id: string; subject_id: string; section_id: string; title: string; kind: string; date: string; maximum_marks: number | null; status: string }[];
  resources: { id: string; subject_id: string; section_id: string; title: string; resource_type: string; status: string }[];
  syllabus: { id: string; subject_id: string; module_number: number; title: string; status: string }[];
}

interface MarkRoster {
  assessment_id: string;
  maximum_marks: number | null;
  records: { student_id: string; usn?: string | null; name: string; marks: number | null }[];
}

interface FacultyAnnouncement {
  id: string;
  title: string;
  body: string;
  published_at: string;
}

const localDateTime = () => {
  const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000);
  return date.toISOString().slice(0, 16);
};

export const FacultyAcademicManagement: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [assignmentKey, setAssignmentKey] = useState('');
  const [moduleTitle, setModuleTitle] = useState('');
  const [resourceTitle, setResourceTitle] = useState('');
  const [moduleNumber, setModuleNumber] = useState('1');
  const [moduleDescription, setModuleDescription] = useState('');
  const [resourceType, setResourceType] = useState('NOTES');
  const [resourceDescription, setResourceDescription] = useState('');
  const [resourceUrl, setResourceUrl] = useState('');
  const [assessmentTitle, setAssessmentTitle] = useState('');
  const [assessmentKind, setAssessmentKind] = useState('INTERNAL');
  const [assessmentDate, setAssessmentDate] = useState(localDateTime);
  const [maximumMarks, setMaximumMarks] = useState('');
  const [selectedAssessmentId, setSelectedAssessmentId] = useState('');
  const [marksByAssessment, setMarksByAssessment] = useState<Record<string, Record<string, string>>>({});
  const [error, setError] = useState('');

  const { data: assignments = [], isLoading, isError } = useQuery<AcademicAssignment[]>({
    queryKey: ['faculty-academic-assignments', user?.id],
    queryFn: async () => (await api.get('/faculty/academic-assignments')).data,
    enabled: Boolean(user?.id),
  });
  const selectedAssignment = useMemo(
    () => assignments.find(item => `${item.subject_id}:${item.section_id}` === assignmentKey),
    [assignments, assignmentKey],
  );
  const { data: content } = useQuery<AcademicContent>({
    queryKey: ['faculty-academic-content', user?.id],
    queryFn: async () => (await api.get('/faculty/academic-content')).data,
    enabled: Boolean(user?.id),
  });
  const { data: announcements = [] } = useQuery<FacultyAnnouncement[]>({
    queryKey: ['faculty-academic-announcements', user?.id],
    queryFn: async () => (await api.get('/faculty/announcements')).data,
    enabled: Boolean(user?.id),
  });
  const visibleAssessments = (content?.assessments || []).filter(item => (
    !selectedAssignment || (item.subject_id === selectedAssignment.subject_id && item.section_id === selectedAssignment.section_id)
  ));
  const { data: marksData } = useQuery<MarkRoster>({
    queryKey: ['faculty-academic-marks', user?.id, selectedAssessmentId],
    queryFn: async () => (await api.get(`/faculty/assessments/${encodeURIComponent(selectedAssessmentId)}/marks`)).data,
    enabled: Boolean(user?.id && selectedAssessmentId),
  });

  const studentMarks = useMemo(() => Object.fromEntries((marksData?.records || []).map(record => [
    record.student_id,
    marksByAssessment[selectedAssessmentId]?.[record.student_id]
      ?? (record.marks == null ? '' : String(record.marks)),
  ])), [marksData, selectedAssessmentId, marksByAssessment]);

  const refreshContent = () => {
    queryClient.invalidateQueries({ queryKey: ['faculty-academic-content', user?.id] });
    setError('');
  };
  const createModule = useMutation({
    mutationFn: async () => api.post('/faculty/syllabus', {
      subject_id: selectedAssignment?.subject_id,
      module_number: Number(moduleNumber),
      title: moduleTitle,
      description: moduleDescription || null,
      sequence: Number(moduleNumber),
      status: 'DRAFT',
    }),
    onSuccess: refreshContent,
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Syllabus module could not be saved.'),
  });
  const createResource = useMutation({
    mutationFn: async () => api.post('/faculty/resources', {
      subject_id: selectedAssignment?.subject_id,
      section_id: selectedAssignment?.section_id,
      title: resourceTitle,
      description: resourceDescription || null,
      resource_type: resourceType,
      url: resourceUrl || null,
      status: 'DRAFT',
    }),
    onSuccess: refreshContent,
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Academic resource could not be saved.'),
  });
  const createAssessment = useMutation({
    mutationFn: async () => (await api.post('/faculty/assessments', {
      subject_id: selectedAssignment?.subject_id,
      section_id: selectedAssignment?.section_id,
      title: assessmentTitle,
      kind: assessmentKind,
      date: new Date(assessmentDate).toISOString(),
      maximum_marks: Number(maximumMarks),
      status: 'DRAFT',
    })).data,
    onSuccess: result => {
      refreshContent();
      setSelectedAssessmentId(result.id);
      setAssessmentTitle('');
    },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Assessment could not be created.'),
  });
  const saveMarks = useMutation({
    mutationFn: async () => api.put(`/faculty/assessments/${encodeURIComponent(selectedAssessmentId)}/marks`, {
      records: Object.entries(studentMarks)
        .filter(([, value]) => value !== '')
        .map(([student_id, value]) => ({ student_id, marks: Number(value) })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faculty-academic-marks', user?.id, selectedAssessmentId] });
      setError('');
    },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Marks could not be saved.'),
  });
  const publishAssessment = useMutation({
    mutationFn: async (assessmentId: string) => api.post(`/faculty/assessments/${encodeURIComponent(assessmentId)}/publish`),
    onSuccess: refreshContent,
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Assessment could not be published.'),
  });
  const publishResource = useMutation({
    mutationFn: async (resourceId: string) => api.post(`/faculty/resources/${encodeURIComponent(resourceId)}/publish`),
    onSuccess: refreshContent,
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Resource could not be published.'),
  });
  const publishModule = useMutation({
    mutationFn: async (moduleId: string) => api.post(`/faculty/syllabus/${encodeURIComponent(moduleId)}/publish`),
    onSuccess: refreshContent,
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'Syllabus module could not be published.'),
  });

  return (
    <section className="max-w-5xl space-y-5">
      <header>
        <h1 className="section-header"><BookOpenCheck size={20} className="text-cyan-300" />Assessments & Learning Materials</h1>
        <p className="text-sm text-slate-400 mt-2">Academic records are available only for your timetable teaching assignments. New items remain drafts until published.</p>
      </header>
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading your teaching assignments…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Your academic assignments could not be loaded.</div>
          : !assignments.length ? <div className="card p-6 text-sm text-slate-400">No subjects or sections are assigned to your faculty account.</div>
            : <>
              <div className="card p-5">
                <label className="block text-xs text-slate-400">Subject and section
                  <select className="input-field mt-2" value={assignmentKey} onChange={event => { setAssignmentKey(event.target.value); setSelectedAssessmentId(''); }}>
                    <option value="">Choose an assigned subject and section</option>
                    {assignments.map(item => <option key={`${item.subject_id}:${item.section_id}`} value={`${item.subject_id}:${item.section_id}`}>{item.subject_code} · {item.section_code} — {item.subject_name}</option>)}
                  </select>
                </label>
              </div>
              {selectedAssignment && <>
                {selectedAssignment.is_synthetic && <p className="badge-amber">SYNTHETIC ACADEMIC CONTEXT</p>}
                <div className="grid lg:grid-cols-2 gap-4">
                  <form className="card p-5 space-y-3" onSubmit={event => { event.preventDefault(); createModule.mutate(); }}>
                    <h2 className="font-semibold text-slate-200">Add syllabus module</h2>
                    <label className="block text-xs text-slate-400">Module number<input className="input-field mt-1" type="number" min="1" value={moduleNumber} onChange={event => setModuleNumber(event.target.value)} required /></label>
                    <label className="block text-xs text-slate-400">Title<input className="input-field mt-1" value={moduleTitle} onChange={event => setModuleTitle(event.target.value)} maxLength={200} required /></label>
                    <label className="block text-xs text-slate-400">Topics / description<textarea className="input-field mt-1" value={moduleDescription} onChange={event => setModuleDescription(event.target.value)} maxLength={5000} /></label>
                    <button className="btn-primary" disabled={createModule.isPending}>{createModule.isPending ? 'Saving…' : 'Save draft module'}</button>
                  </form>
                  <form className="card p-5 space-y-3" onSubmit={event => { event.preventDefault(); createResource.mutate(); }}>
                    <h2 className="font-semibold text-slate-200">Add academic resource</h2>
                    <label className="block text-xs text-slate-400">Resource title<input className="input-field mt-1" value={resourceTitle} onChange={event => setResourceTitle(event.target.value)} maxLength={200} required /></label>
                    <label className="block text-xs text-slate-400">Type<select className="input-field mt-1" value={resourceType} onChange={event => setResourceType(event.target.value)}>{['NOTES', 'PDF', 'LINK', 'VIDEO', 'ASSIGNMENT', 'REFERENCE'].map(type => <option key={type}>{type}</option>)}</select></label>
                    <label className="block text-xs text-slate-400">URL (optional)<input className="input-field mt-1" type="url" value={resourceUrl} onChange={event => setResourceUrl(event.target.value)} maxLength={2000} /></label>
                    <label className="block text-xs text-slate-400">Description or text<input className="input-field mt-1" value={resourceDescription} onChange={event => setResourceDescription(event.target.value)} maxLength={5000} /></label>
                    <button className="btn-primary" disabled={createResource.isPending}>{createResource.isPending ? 'Saving…' : 'Save draft resource'}</button>
                  </form>
                </div>
                <form className="card p-5 grid md:grid-cols-2 gap-3" onSubmit={event => { event.preventDefault(); createAssessment.mutate(); }}>
                  <h2 className="font-semibold text-slate-200 md:col-span-2">Create assessment</h2>
                  <label className="text-xs text-slate-400">Title<input className="input-field mt-1" value={assessmentTitle} onChange={event => setAssessmentTitle(event.target.value)} maxLength={200} required /></label>
                  <label className="text-xs text-slate-400">Type<select className="input-field mt-1" value={assessmentKind} onChange={event => setAssessmentKind(event.target.value)}>{['INTERNAL', 'QUIZ', 'ASSIGNMENT', 'LAB', 'PROJECT', 'EXAM', 'OTHER'].map(type => <option key={type}>{type}</option>)}</select></label>
                  <label className="text-xs text-slate-400">Date and time<input className="input-field mt-1" type="datetime-local" value={assessmentDate} onChange={event => setAssessmentDate(event.target.value)} required /></label>
                  <label className="text-xs text-slate-400">Maximum marks<input className="input-field mt-1" type="number" min="0.01" step="0.01" value={maximumMarks} onChange={event => setMaximumMarks(event.target.value)} required /></label>
                  <button className="btn-primary md:col-span-2 w-fit" disabled={createAssessment.isPending}>{createAssessment.isPending ? 'Creating…' : 'Create draft assessment'}</button>
                </form>
                <div className="card p-5 space-y-3">
                  <h2 className="font-semibold text-slate-200">Your assessments</h2>
                  {!visibleAssessments.length ? <p className="text-sm text-slate-400">No assessments are recorded for this assignment.</p>
                    : visibleAssessments.map(item => <article key={item.id} className="rounded-lg border border-slate-800 p-4 flex flex-wrap items-center justify-between gap-3">
                      <div><p className="text-sm text-slate-200">{item.title} · {item.kind}</p><p className="text-xs text-slate-500 mt-1">{new Date(item.date).toLocaleString()} · {item.maximum_marks ?? 'Maximum marks unavailable'} · {item.status}</p></div>
                      <div className="flex gap-2"><button className="btn-secondary" onClick={() => setSelectedAssessmentId(item.id)}>Manage marks</button>{item.status !== 'PUBLISHED' && <button className="btn-primary" onClick={() => publishAssessment.mutate(item.id)} disabled={publishAssessment.isPending}>Publish</button>}</div>
                    </article>)}
                </div>
                {selectedAssessmentId && <div className="card p-5 space-y-4">
                  <div className="flex justify-between gap-3"><div><h2 className="font-semibold text-slate-200">Enter or update marks</h2><p className="text-xs text-slate-400 mt-1">Marks stay hidden from students until the assessment is published.</p></div><button className="btn-primary" disabled={saveMarks.isPending || !marksData?.records.length} onClick={() => { if (window.confirm('Save marks for the entered students?')) saveMarks.mutate(); }}>{saveMarks.isPending ? 'Saving…' : 'Save marks'}</button></div>
                  {!marksData ? <p className="text-sm text-slate-400">Loading the authorized student roster…</p>
                    : <div className="divide-y divide-slate-800">{marksData.records.map(record => <label key={record.student_id} className="flex items-center justify-between gap-4 py-3"><span className="text-sm text-slate-200">{record.name}<span className="block text-xs text-slate-500">{record.usn || 'USN unavailable'}</span></span><input className="input-field max-w-36" type="number" min="0" max={marksData.maximum_marks ?? undefined} step="0.01" aria-label={`Marks for ${record.name}`} value={studentMarks[record.student_id] || ''} onChange={event => setMarksByAssessment(current => ({
                      ...current,
                      [selectedAssessmentId]: { ...current[selectedAssessmentId], [record.student_id]: event.target.value },
                    }))} placeholder={`/${marksData.maximum_marks ?? 'max'}`} /></label>)}</div>}
                </div>}
              </>}
              {content && <div className="grid md:grid-cols-2 gap-4">
                <div className="card p-5"><h2 className="font-semibold text-slate-200">Resources</h2>{content.resources.length ? <ul className="mt-3 space-y-2">{content.resources.filter(item => !selectedAssignment || (item.subject_id === selectedAssignment.subject_id && item.section_id === selectedAssignment.section_id)).map(item => <li key={item.id} className="flex items-center justify-between gap-3 text-sm"><span className="text-slate-300">{item.title} · {item.status}</span>{item.status !== 'PUBLISHED' && <button className="btn-secondary" onClick={() => publishResource.mutate(item.id)} disabled={publishResource.isPending}>Publish</button>}</li>)}</ul> : <p className="text-sm text-slate-400 mt-2">No resources have been added yet.</p>}</div>
                <div className="card p-5"><h2 className="font-semibold text-slate-200">Syllabus modules</h2>{content.syllabus.length ? <ul className="mt-3 space-y-2">{content.syllabus.filter(item => !selectedAssignment || item.subject_id === selectedAssignment.subject_id).map(item => <li key={item.id} className="flex items-center justify-between gap-3 text-sm"><span className="text-slate-300">Module {item.module_number}: {item.title} · {item.status}</span>{item.status !== 'PUBLISHED' && <button className="btn-secondary" onClick={() => publishModule.mutate(item.id)} disabled={publishModule.isPending}>Publish</button>}</li>)}</ul> : <p className="text-sm text-slate-400 mt-2">No syllabus modules have been added yet.</p>}</div>
              </div>}
              <div className="card p-5">
                <h2 className="font-semibold text-slate-200">Faculty announcements</h2>
                {announcements.length ? <ul className="mt-3 space-y-3">{announcements.map(item => <li key={item.id} className="border-t border-slate-800 pt-3"><p className="text-sm font-medium text-white">{item.title}</p><p className="text-sm text-slate-300 mt-1 whitespace-pre-wrap">{item.body}</p><time className="text-xs text-slate-500">{new Date(item.published_at).toLocaleString()}</time></li>)}</ul>
                  : <p className="text-sm text-slate-400 mt-2">No announcements are available for your role or teaching sections.</p>}
              </div>
            </>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </section>
  );
};

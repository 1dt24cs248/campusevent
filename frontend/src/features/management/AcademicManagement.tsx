import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { BookOpenCheck, Pencil, Plus, RotateCcw } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { isValidationRecord } from './academicRecordProvenance';

interface Department {
  id: string;
  name: string;
  section_count: number;
  subject_count: number;
}

interface Section {
  id: string;
  code: string;
  name: string;
  department_id: string;
  department: string | null;
  year: number;
  strength: number;
  student_count: number;
  students: { student_id: string; usn: string | null; name: string | null }[];
  teaching_assignments: {
    faculty_id: string;
    faculty_name: string;
    subject_id: string;
    subject_code: string;
    subject_name: string;
    section_id: string;
    section_code: string;
    timetable_entry_count: number;
  }[];
  is_synthetic: boolean;
  provenance?: string | null;
}

interface Subject {
  id: string;
  code: string;
  name: string;
  department_id: string | null;
  credits: number | null;
  description: string | null;
  kind: string | null;
  faculty: string[];
  sections: string[];
  is_synthetic: boolean;
  provenance?: string | null;
}

interface AcademicOverview {
  departments: Department[];
  sections: Section[];
  subjects: Subject[];
  student_section_assignments: { student_id: string; usn?: string | null; name?: string | null; section_id?: string | null }[];
  faculty_subject_section_assignments: {
    faculty_id: string;
    faculty_name: string;
    subject_id: string;
    subject_code: string;
    subject_name: string;
    section_id: string;
    section_code: string;
    timetable_entry_count: number;
  }[];
  upcoming_assessments: { id: string; title: string; date: string; section_id: string; subject_id: string; status: string }[];
  attendance_sessions: { id: string; session_date: string; status: string; section_id: string; subject_id: string }[];
  recent_activity: { id: string; actor: string; action: string; entity_type: string; entity_id: string; timestamp: string }[];
  announcements: { id: string; title: string; body: string; section_id?: string | null; audience?: string[] | Record<string, unknown> | null; creator: string; status: string; published_at: string }[];
}

interface ManagementOverview {
  students: { total: number; active: number };
  faculty: { total: number; active: number };
  departments: number;
  sections: number;
  subjects: number;
  rooms: number;
  today_classes: number;
  pending_classroom_requests: number;
  pending_event_proposals: number;
  upcoming_assessments: number;
  attendance_sessions_today: number;
  published_announcements: number;
}

interface SectionForm {
  code: string;
  name: string;
  department_id: string;
  year: string;
  strength: string;
}

interface SubjectForm {
  code: string;
  name: string;
  department_id: string;
  credits: string;
  description: string;
  kind: string;
}

const EMPTY_SECTION: SectionForm = { code: '', name: '', department_id: '', year: '1', strength: '' };
const EMPTY_SUBJECT: SubjectForm = { code: '', name: '', department_id: '', credits: '', description: '', kind: '' };

export const AcademicManagement: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [departmentName, setDepartmentName] = useState('');
  const [editingDepartment, setEditingDepartment] = useState('');
  const [sectionForm, setSectionForm] = useState<SectionForm>(EMPTY_SECTION);
  const [editingSection, setEditingSection] = useState('');
  const [subjectForm, setSubjectForm] = useState<SubjectForm>(EMPTY_SUBJECT);
  const [editingSubject, setEditingSubject] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [audience, setAudience] = useState('STUDENT');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const { data: overview, isLoading: overviewLoading, isError: overviewError } = useQuery<ManagementOverview>({
    queryKey: ['management-overview', user?.id],
    queryFn: async () => (await api.get('/management/overview')).data,
    enabled: Boolean(user?.id),
  });
  const { data, isLoading, isError } = useQuery<AcademicOverview>({
    queryKey: ['management-academic-overview', user?.id],
    queryFn: async () => (await api.get('/management/academics')).data,
    enabled: Boolean(user?.id),
  });

  const refresh = async () => {
    setError('');
    setNotice('Institutional records updated.');
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['management-academic-overview', user?.id] }),
      queryClient.invalidateQueries({ queryKey: ['management-overview', user?.id] }),
      queryClient.invalidateQueries({ queryKey: ['management-departments'] }),
      queryClient.invalidateQueries({ queryKey: ['management-sections'] }),
      queryClient.invalidateQueries({ queryKey: ['management-sections-filter'] }),
      queryClient.invalidateQueries({ queryKey: ['management-students'] }),
      queryClient.invalidateQueries({ queryKey: ['management-faculty'] }),
    ]);
  };
  const failure = (mutationError: unknown, fallback: string) => {
    setNotice('');
    const detail = mutationError instanceof AxiosError
      ? mutationError.response?.data?.detail
      : undefined;
    setError(typeof detail === 'string' ? detail : fallback);
  };

  const departmentMutation = useMutation({
    mutationFn: async () => editingDepartment
      ? api.patch(`/management/departments/${encodeURIComponent(editingDepartment)}`, { name: departmentName })
      : api.post('/management/departments', { name: departmentName }),
    onSuccess: async () => { setDepartmentName(''); setEditingDepartment(''); await refresh(); },
    onError: mutationError => failure(mutationError, 'Department could not be saved.'),
  });
  const sectionMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...sectionForm,
        year: Number(sectionForm.year),
        strength: Number(sectionForm.strength),
      };
      return editingSection
        ? api.patch(`/management/sections/${encodeURIComponent(editingSection)}`, payload)
        : api.post('/management/sections', payload);
    },
    onSuccess: async () => { setSectionForm(EMPTY_SECTION); setEditingSection(''); await refresh(); },
    onError: mutationError => failure(mutationError, 'Section could not be saved.'),
  });
  const subjectMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...subjectForm,
        department_id: subjectForm.department_id || null,
        credits: subjectForm.credits === '' ? null : Number(subjectForm.credits),
        description: subjectForm.description.trim() || null,
        kind: subjectForm.kind.trim() || null,
      };
      return editingSubject
        ? api.patch(`/management/subjects/${encodeURIComponent(editingSubject)}`, payload)
        : api.post('/management/subjects', payload);
    },
    onSuccess: async () => { setSubjectForm(EMPTY_SUBJECT); setEditingSubject(''); await refresh(); },
    onError: mutationError => failure(mutationError, 'Subject could not be saved.'),
  });
  const createAnnouncement = useMutation({
    mutationFn: async () => api.post('/management/announcements', {
      title,
      body,
      audience: [audience],
      section_id: sectionId || null,
    }),
    onSuccess: async () => {
      setTitle('');
      setBody('');
      setNotice('Announcement published.');
      setError('');
      await queryClient.invalidateQueries({ queryKey: ['management-academic-overview', user?.id] });
    },
    onError: mutationError => failure(mutationError, 'Announcement could not be published.'),
  });

  const startDepartmentEdit = (department: Department) => {
    setDepartmentName(department.name);
    setEditingDepartment(department.id);
  };
  const startSectionEdit = (section: Section) => {
    setSectionForm({
      code: section.code,
      name: section.name,
      department_id: section.department_id,
      year: String(section.year),
      strength: String(section.strength),
    });
    setEditingSection(section.id);
  };
  const startSubjectEdit = (subject: Subject) => {
    setSubjectForm({
      code: subject.code,
      name: subject.name,
      department_id: subject.department_id || '',
      credits: subject.credits == null ? '' : String(subject.credits),
      description: subject.description || '',
      kind: subject.kind || '',
    });
    setEditingSubject(subject.id);
  };

  return (
    <section className="max-w-7xl space-y-5">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Institutional administration</p>
        <h1 className="section-header mt-1"><BookOpenCheck size={20} className="text-indigo-300" />Academic Management</h1>
        <p className="text-sm text-slate-400 mt-2">Manage academic master records and review timetable-derived teaching relationships. Existing assignments are not independently duplicated.</p>
      </header>
      {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      {overviewLoading ? <div className="card p-5 text-sm text-slate-400">Loading institutional overview…</div>
        : overviewError || !overview ? <div role="alert" className="card p-5 text-sm text-red-300">Institutional overview could not be loaded.</div>
          : <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
            {[
              ['Students', `${overview.students.active} active / ${overview.students.total}`],
              ['Faculty', `${overview.faculty.active} active / ${overview.faculty.total}`],
              ['Departments', overview.departments],
              ['Sections', overview.sections],
              ['Subjects', overview.subjects],
              ['Rooms', overview.rooms],
              ["Today's classes", overview.today_classes],
              ['Pending requests', overview.pending_classroom_requests],
              ['Event proposals', overview.pending_event_proposals],
              ['Upcoming assessments', overview.upcoming_assessments],
              ['Attendance today', overview.attendance_sessions_today],
              ['Announcements', overview.published_announcements],
            ].map(([label, value]) => <article key={String(label)} className="card p-4">
              <p className="text-xs text-slate-500">{label}</p><p className="text-lg font-semibold text-white mt-1">{value}</p>
            </article>)}
          </div>}

      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading academic directory…</div>
        : isError || !data ? <div role="alert" className="card p-5 text-sm text-red-300">Academic directory could not be loaded.</div>
          : <>
            <div className="grid xl:grid-cols-3 gap-4">
              <section className="card p-5 space-y-3">
                <h2 className="font-semibold text-slate-200">Departments</h2>
                <form className="flex gap-2" onSubmit={event => { event.preventDefault(); departmentMutation.mutate(); }}>
                  <input className="input-field" aria-label="Department name" value={departmentName} onChange={event => setDepartmentName(event.target.value)} placeholder="Department name" maxLength={160} required />
                  <button className="btn-primary flex items-center gap-1" disabled={departmentMutation.isPending}><Plus size={14} />{editingDepartment ? 'Save' : 'Add'}</button>
                </form>
                {editingDepartment && <button className="text-xs text-slate-400 inline-flex items-center gap-1" onClick={() => { setEditingDepartment(''); setDepartmentName(''); }}><RotateCcw size={12} />Cancel edit</button>}
                <div className="overflow-x-auto"><table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500"><th className="py-2">DEPARTMENT</th><th>SECTIONS</th><th>SUBJECTS</th><th /></tr></thead>
                  <tbody>{data.departments.map(department => <tr key={department.id} className="border-b border-slate-800/60">
                    <td className="py-2 text-slate-200">{department.name}</td><td>{department.section_count}</td><td>{department.subject_count}</td>
                    <td><button aria-label={`Edit ${department.name}`} className="text-indigo-300" onClick={() => startDepartmentEdit(department)}><Pencil size={14} /></button></td>
                  </tr>)}</tbody>
                </table>{!data.departments.length && <p className="py-3 text-sm text-slate-500">No departments recorded.</p>}</div>
              </section>

              <section className="card p-5 space-y-3">
                <h2 className="font-semibold text-slate-200">Sections</h2>
                <form className="grid grid-cols-2 gap-2" onSubmit={event => { event.preventDefault(); sectionMutation.mutate(); }}>
                  <input className="input-field" aria-label="Section code" placeholder="Section code" value={sectionForm.code} onChange={event => setSectionForm({ ...sectionForm, code: event.target.value })} required />
                  <input className="input-field" aria-label="Section name" placeholder="Section name" value={sectionForm.name} onChange={event => setSectionForm({ ...sectionForm, name: event.target.value })} required />
                  <select className="input-field col-span-2" aria-label="Section department" value={sectionForm.department_id} onChange={event => setSectionForm({ ...sectionForm, department_id: event.target.value })} required>
                    <option value="">Select department</option>{data.departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
                  </select>
                  <label className="text-xs text-slate-500">Year<input className="input-field mt-1" type="number" min="1" max="8" value={sectionForm.year} onChange={event => setSectionForm({ ...sectionForm, year: event.target.value })} required /></label>
                  <label className="text-xs text-slate-500">Strength<input className="input-field mt-1" type="number" min="1" max="1000" value={sectionForm.strength} onChange={event => setSectionForm({ ...sectionForm, strength: event.target.value })} required /></label>
                  <button className="btn-primary col-span-2 w-fit" disabled={sectionMutation.isPending}>{editingSection ? 'Save section' : 'Add section'}</button>
                </form>
                {editingSection && <button className="text-xs text-slate-400 inline-flex items-center gap-1" onClick={() => { setEditingSection(''); setSectionForm(EMPTY_SECTION); }}><RotateCcw size={12} />Cancel edit</button>}
                <div className="overflow-x-auto max-h-72 overflow-y-auto"><table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500"><th className="py-2">SECTION</th><th>DEPT / YEAR</th><th>ROSTER</th><th /></tr></thead>
                  <tbody>{data.sections.map(section => <tr key={section.id} className="border-b border-slate-800/60 align-top">
                    <td className="py-2 text-slate-200">{section.code}{isValidationRecord(section.is_synthetic, section.provenance) && <span className="badge-amber ml-2">Synthetic / Validation</span>}<span className="block text-xs text-slate-500">{section.name}</span></td>
                    <td className="py-2 text-xs text-slate-400">{section.department || 'Unassigned'} · Year {section.year}</td>
                    <td className="py-2 text-xs text-slate-400">{section.student_count} students / {section.strength} capacity<span className="block text-slate-500">{section.teaching_assignments.map(item => `${item.subject_code} · ${item.faculty_name || 'Faculty unassigned'}`).join('; ') || 'No timetable assignments'}</span></td>
                    <td className="py-2"><button aria-label={`Edit ${section.code}`} className="text-indigo-300" onClick={() => startSectionEdit(section)}><Pencil size={14} /></button></td>
                  </tr>)}</tbody>
                </table>{!data.sections.length && <p className="py-3 text-sm text-slate-500">No sections recorded.</p>}</div>
              </section>

              <section className="card p-5 space-y-3">
                <h2 className="font-semibold text-slate-200">Subjects</h2>
                <form className="grid grid-cols-2 gap-2" onSubmit={event => { event.preventDefault(); subjectMutation.mutate(); }}>
                  <input className="input-field" aria-label="Subject code" placeholder="Subject code" value={subjectForm.code} onChange={event => setSubjectForm({ ...subjectForm, code: event.target.value })} required />
                  <input className="input-field" aria-label="Subject name" placeholder="Subject name" value={subjectForm.name} onChange={event => setSubjectForm({ ...subjectForm, name: event.target.value })} required />
                  <select className="input-field" aria-label="Subject department" value={subjectForm.department_id} onChange={event => setSubjectForm({ ...subjectForm, department_id: event.target.value })}>
                    <option value="">No department</option>{data.departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
                  </select>
                  <input className="input-field" aria-label="Subject credits" placeholder="Credits" type="number" min="0" max="100" value={subjectForm.credits} onChange={event => setSubjectForm({ ...subjectForm, credits: event.target.value })} />
                  <textarea className="input-field col-span-2" aria-label="Subject description" placeholder="Description (optional)" maxLength={5000} value={subjectForm.description} onChange={event => setSubjectForm({ ...subjectForm, description: event.target.value })} />
                  <input className="input-field col-span-2" aria-label="Subject kind" placeholder="Subject type (optional)" maxLength={40} value={subjectForm.kind} onChange={event => setSubjectForm({ ...subjectForm, kind: event.target.value })} />
                  <button className="btn-primary col-span-2 w-fit" disabled={subjectMutation.isPending}>{editingSubject ? 'Save subject' : 'Add subject'}</button>
                </form>
                {editingSubject && <button className="text-xs text-slate-400 inline-flex items-center gap-1" onClick={() => { setEditingSubject(''); setSubjectForm(EMPTY_SUBJECT); }}><RotateCcw size={12} />Cancel edit</button>}
                <div className="overflow-x-auto max-h-72 overflow-y-auto"><table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500"><th className="py-2">SUBJECT</th><th>DEPARTMENT</th><th>TEACHING</th><th /></tr></thead>
                  <tbody>{data.subjects.map(subject => <tr key={subject.id} className="border-b border-slate-800/60 align-top">
                    <td className="py-2 text-slate-200">{subject.code}{isValidationRecord(subject.is_synthetic, subject.provenance) && <span className="badge-amber ml-2">Synthetic / Validation</span>}<span className="block text-xs text-slate-500">{subject.name}{subject.credits == null ? '' : ` · ${subject.credits} credits`}</span></td>
                    <td className="py-2 text-xs text-slate-400">{data.departments.find(item => item.id === subject.department_id)?.name || 'Not assigned'}</td>
                    <td className="py-2 text-xs text-slate-400">{subject.faculty.join(', ') || 'No faculty'}<span className="block text-slate-500">{subject.sections.join(', ') || 'No sections'}</span></td>
                    <td className="py-2"><button aria-label={`Edit ${subject.code}`} className="text-indigo-300" onClick={() => startSubjectEdit(subject)}><Pencil size={14} /></button></td>
                  </tr>)}</tbody>
                </table>{!data.subjects.length && <p className="py-3 text-sm text-slate-500">No subjects recorded.</p>}</div>
              </section>
            </div>

            <section className="card p-5">
              <h2 className="font-semibold text-slate-200">Faculty → subject → section</h2>
              {data.faculty_subject_section_assignments.length ? <div className="overflow-x-auto mt-3"><table className="w-full text-sm">
                <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500"><th className="py-2">FACULTY</th><th>SUBJECT</th><th>SECTION</th><th>CLASSES / WEEK</th></tr></thead>
                <tbody>{data.faculty_subject_section_assignments.map((row, index) => <tr key={`${row.faculty_id}-${row.subject_id}-${row.section_id}-${index}`} className="border-b border-slate-800/60">
                  <td className="py-2">{row.faculty_name}</td><td>{row.subject_code} · {row.subject_name}</td><td>{row.section_code}</td><td>{row.timetable_entry_count}</td>
                </tr>)}</tbody>
              </table></div> : <p className="mt-3 text-sm text-slate-400">No faculty / subject / section timetable relationships are recorded.</p>}
            </section>

            <div className="grid xl:grid-cols-2 gap-4">
              <section className="card p-5">
                <h2 className="font-semibold text-slate-200">Academic activity</h2>
                <h3 className="mt-4 text-xs uppercase tracking-wide text-slate-500">Upcoming published assessments</h3>
                {data.upcoming_assessments.length ? <ul className="mt-2 divide-y divide-slate-800">{data.upcoming_assessments.map(item => <li key={item.id} className="py-2 text-sm"><span className="text-slate-200">{item.title}</span><span className="ml-2 text-xs text-slate-500">{new Date(item.date).toLocaleString()}</span></li>)}</ul> : <p className="mt-2 text-sm text-slate-400">No upcoming published assessments.</p>}
                <h3 className="mt-4 text-xs uppercase tracking-wide text-slate-500">Recent attendance sessions</h3>
                {data.attendance_sessions.length ? <ul className="mt-2 divide-y divide-slate-800">{data.attendance_sessions.slice(0, 8).map(item => <li key={item.id} className="py-2 text-sm text-slate-300">{item.session_date} · {item.status}</li>)}</ul> : <p className="mt-2 text-sm text-slate-400">No attendance sessions are recorded.</p>}
                <h3 className="mt-4 text-xs uppercase tracking-wide text-slate-500">Recent institutional changes</h3>
                {data.recent_activity.length ? <ul className="mt-2 divide-y divide-slate-800">{data.recent_activity.slice(0, 8).map(item => <li key={item.id} className="py-2 text-sm text-slate-300">{item.action.replaceAll('_', ' ')} · {item.entity_type} · {item.actor}<span className="block text-xs text-slate-500">{new Date(item.timestamp).toLocaleString()}</span></li>)}</ul> : <p className="mt-2 text-sm text-slate-400">No academic administration activity is recorded yet.</p>}
              </section>

              <section className="card p-5 space-y-3">
                <h2 className="font-semibold text-slate-200">Publish an announcement</h2>
                <form className="space-y-3" onSubmit={event => { event.preventDefault(); createAnnouncement.mutate(); }}>
                  <label className="block text-xs text-slate-400">Title<input className="input-field mt-1" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} required /></label>
                  <label className="block text-xs text-slate-400">Content<textarea className="input-field mt-1 min-h-24" value={body} onChange={event => setBody(event.target.value)} maxLength={5000} required /></label>
                  <label className="block text-xs text-slate-400">Audience<select className="input-field mt-1" value={audience} onChange={event => setAudience(event.target.value)}>
                    <option value="STUDENT">All students</option><option value="FACULTY">All faculty</option><option value="MANAGEMENT">Management</option><option value="ALL">All users</option>
                  </select></label>
                  <label className="block text-xs text-slate-400">Section (optional)<select className="input-field mt-1" value={sectionId} onChange={event => setSectionId(event.target.value)}><option value="">All sections for this audience</option>{data.sections.map(section => <option key={section.id} value={section.id}>{section.code}</option>)}</select></label>
                  <button className="btn-primary" disabled={createAnnouncement.isPending}>{createAnnouncement.isPending ? 'Publishing…' : 'Publish announcement'}</button>
                </form>
                <h3 className="pt-3 text-xs uppercase tracking-wide text-slate-500">Published announcements</h3>
                {data.announcements.length ? <ul className="divide-y divide-slate-800">{data.announcements.slice(0, 10).map(item => {
                  const audienceLabel = Array.isArray(item.audience) ? item.audience.join(', ') : item.audience ? JSON.stringify(item.audience) : 'All users';
                  return <li key={item.id} className="py-3"><p className="text-sm font-medium text-white">{item.title}</p><p className="text-xs text-slate-400 mt-1">{audienceLabel}{item.section_id ? ` · ${data.sections.find(section => section.id === item.section_id)?.code || 'Specific section'}` : ''} · {item.status} · By {item.creator}</p><time className="text-xs text-slate-500">{new Date(item.published_at).toLocaleString()}</time><p className="text-sm text-slate-300 mt-2 whitespace-pre-wrap">{item.body}</p></li>;
                })}</ul> : <p className="text-sm text-slate-400">No announcements have been published.</p>}
              </section>
            </div>
          </>}
    </section>
  );
};

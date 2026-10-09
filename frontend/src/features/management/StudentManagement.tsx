import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { AlertCircle, Plus, RotateCcw, Search, UserRound, X } from 'lucide-react';
import api from '../../api/client';

interface Department {
  id: string;
  name: string;
}

interface Section {
  id: string;
  code: string;
  department_id: string;
  synthetic: boolean;
}

interface Student {
  id: string;
  usn: string | null;
  email: string;
  name: string;
  phone: string | null;
  department_id: string;
  department: string;
  program: string | null;
  semester: number | null;
  section_id: string;
  section: string;
  admission_year: number | null;
  academic_status: string | null;
  active: boolean;
  synthetic_section: boolean;
}

interface StudentForm {
  usn: string;
  email: string;
  password: string;
  name: string;
  phone: string;
  department_id: string;
  program: string;
  semester: string;
  section_id: string;
  admission_year: string;
  academic_status: string;
}

const EMPTY_FORM: StudentForm = {
  usn: '', email: '', password: '', name: '', phone: '',
  department_id: '', program: '', semester: '', section_id: '',
  admission_year: '', academic_status: 'ACTIVE',
};

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

export const StudentManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [semesterFilter, setSemesterFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [academicStatusFilter, setAcademicStatusFilter] = useState('');
  const [selected, setSelected] = useState<Student | null>(null);
  const [form, setForm] = useState<StudentForm>(EMPTY_FORM);
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState('');
  const [formError, setFormError] = useState('');

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ['management-departments'],
    queryFn: async () => (await api.get('/management/departments')).data,
  });
  const { data: sections = [] } = useQuery<Section[]>({
    queryKey: ['management-sections', form.department_id],
    queryFn: async () => (await api.get('/management/sections', {
      params: form.department_id ? { department_id: form.department_id } : {},
    })).data,
  });
  const { data: filterSections = [] } = useQuery<Section[]>({
    queryKey: ['management-sections-filter', departmentFilter],
    queryFn: async () => (await api.get('/management/sections', {
      params: departmentFilter ? { department_id: departmentFilter } : {},
    })).data,
  });
  const { data, isLoading, isError } = useQuery<{ items: Student[]; total: number }>({
    queryKey: ['management-students', search, departmentFilter, semesterFilter, sectionFilter, activeFilter, academicStatusFilter],
    queryFn: async () => (await api.get('/management/students', {
      params: {
        ...(search.trim() ? { q: search.trim() } : {}),
        ...(departmentFilter ? { department_id: departmentFilter } : {}),
        ...(semesterFilter ? { semester: Number(semesterFilter) } : {}),
        ...(sectionFilter ? { section_id: sectionFilter } : {}),
        ...(activeFilter ? { active: activeFilter === 'active' } : {}),
        ...(academicStatusFilter ? { academic_status: academicStatusFilter } : {}),
      },
    })).data,
  });

  const resetForm = () => {
    setSelected(null);
    setForm(EMPTY_FORM);
    setPassword('');
    setFormError('');
  };
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['management-students'] });
    await queryClient.invalidateQueries({ queryKey: ['management-sections'] });
  };
  const createStudent = useMutation({
    mutationFn: async () => api.post('/management/students', {
      ...form,
      semester: Number(form.semester),
      admission_year: Number(form.admission_year),
      phone: form.phone.trim() || null,
    }),
    onSuccess: async () => {
      setFeedback('Student identity created.');
      resetForm();
      await refresh();
    },
    onError: error => setFormError(errorMessage(error, 'Unable to create student.')),
  });
  const updateStudent = useMutation({
    mutationFn: async () => api.patch(`/management/students/${encodeURIComponent(selected!.id)}`, {
      usn: form.usn,
      email: form.email,
      name: form.name,
      phone: form.phone.trim() || null,
      department_id: form.department_id,
      program: form.program,
      semester: Number(form.semester),
      section_id: form.section_id,
      admission_year: Number(form.admission_year),
      academic_status: form.academic_status,
    }),
    onSuccess: async () => {
      setFeedback('Student profile updated.');
      resetForm();
      await refresh();
    },
    onError: error => setFormError(errorMessage(error, 'Unable to update student.')),
  });
  const setStudentActive = useMutation({
    mutationFn: async (student: Student) => api.patch(`/management/students/${encodeURIComponent(student.id)}`, { active: !student.active }),
    onSuccess: async (_result, student) => {
      setFeedback(`${student.active ? 'Student deactivated' : 'Student reactivated'}.`);
      await refresh();
    },
    onError: error => setFeedback(errorMessage(error, 'Unable to update student status.')),
  });
  const resetStudentPassword = useMutation({
    mutationFn: async () => api.post(`/management/students/${encodeURIComponent(selected!.id)}/password`, { password }),
    onSuccess: async () => {
      setPassword('');
      setFeedback('Student password reset.');
    },
    onError: error => setFormError(errorMessage(error, 'Unable to reset student password.')),
  });

  const beginEdit = (student: Student) => {
    setSelected(student);
    setForm({
      usn: student.usn || '',
      email: student.email,
      password: '',
      name: student.name,
      phone: student.phone || '',
      department_id: student.department_id,
      program: student.program || '',
      semester: student.semester == null ? '' : String(student.semester),
      section_id: student.section_id,
      admission_year: student.admission_year == null ? '' : String(student.admission_year),
      academic_status: student.academic_status || 'ACTIVE',
    });
    setFormError('');
    setFeedback('');
  };

  const busy = createStudent.isPending || updateStudent.isPending;
  const sectionsForFilter = departmentFilter
    ? filterSections.filter(section => section.department_id === departmentFilter)
    : filterSections;

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Institutional administration</p>
          <h1 className="text-2xl font-bold text-white mt-1">Student Management</h1>
          <p className="text-sm text-slate-400 mt-1">Provision and maintain student institutional identities.</p>
        </div>
        <button type="button" className="btn-primary flex items-center gap-2" onClick={resetForm}>
          <Plus size={16} /> Add student
        </button>
      </header>

      {feedback && <p role="status" className="text-sm text-emerald-300">{feedback}</p>}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.8fr)] gap-6">
        <section className="card p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-6 gap-3">
            <label className="relative text-xs text-slate-400 sm:col-span-2 xl:col-span-1">
              Search
              <Search size={14} className="absolute left-3 top-8 text-slate-500" />
              <input className="input-field mt-1 pl-9" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name, USN, email" />
            </label>
            <label className="text-xs text-slate-400">Department
              <select className="input-field mt-1" value={departmentFilter} onChange={event => { setDepartmentFilter(event.target.value); setSectionFilter(''); }}>
                <option value="">All departments</option>
                {departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">Semester
              <select className="input-field mt-1" value={semesterFilter} onChange={event => setSemesterFilter(event.target.value)}>
                <option value="">All semesters</option>
                {Array.from({ length: 8 }, (_, index) => index + 1).map(semester => <option key={semester} value={semester}>{semester}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">Section
              <select className="input-field mt-1" value={sectionFilter} onChange={event => setSectionFilter(event.target.value)}>
                <option value="">All sections</option>
                {sectionsForFilter.map(section => <option key={section.id} value={section.id}>{section.code}{section.synthetic ? ' · sample' : ''}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">Account
              <select className="input-field mt-1" value={activeFilter} onChange={event => setActiveFilter(event.target.value)}>
                <option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option>
              </select>
            </label>
            <label className="text-xs text-slate-400">Academic status
              <select className="input-field mt-1" value={academicStatusFilter} onChange={event => setAcademicStatusFilter(event.target.value)}>
                <option value="">All statuses</option><option value="ACTIVE">Active</option><option value="ON_LEAVE">On leave</option><option value="GRADUATED">Graduated</option><option value="WITHDRAWN">Withdrawn</option>
              </select>
            </label>
          </div>
          {isError ? <p role="alert" className="text-sm text-red-300">Student records could not be loaded.</p>
            : isLoading ? <p className="text-sm text-slate-500">Loading student records…</p>
              : !data?.items.length ? <p className="text-sm text-slate-500 py-8 text-center">No student records match these filters.</p>
                : <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500">
                      <th className="py-3 pr-3">STUDENT</th><th className="py-3 pr-3">ACADEMICS</th><th className="py-3 pr-3">STATUS</th><th className="py-3">ACTION</th>
                    </tr></thead>
                    <tbody>{data.items.map(student => (
                      <tr key={student.id} className="border-b border-slate-800/60 align-top">
                        <td className="py-3 pr-3">
                          <button type="button" className="text-left" onClick={() => beginEdit(student)}>
                            <span className="block font-semibold text-white">{student.name || 'Name not provided'}</span>
                            <span className="block text-xs text-cyan-300 mt-1">{student.usn || 'USN not provisioned'}</span>
                            <span className="block text-xs text-slate-500 mt-1">{student.email}</span>
                          </button>
                        </td>
                        <td className="py-3 pr-3 text-xs text-slate-400">
                          {student.department} · Sem {student.semester ?? '—'} · {student.section}
                          {student.synthetic_section && <span className="block text-amber-300 mt-1">Sample section</span>}
                        </td>
                        <td className="py-3 pr-3"><span className={student.active ? 'badge-green' : 'badge-red'}>{student.active ? 'Active' : 'Inactive'}</span></td>
                        <td className="py-3">
                          <button type="button" className="text-xs text-indigo-300 hover:text-indigo-200" onClick={() => setStudentActive.mutate(student)}>
                            {student.active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        </td>
                      </tr>
                    ))}</tbody>
                  </table>
                  <p className="text-xs text-slate-500 mt-3">{data.total} record{data.total === 1 ? '' : 's'}</p>
                </div>}
        </section>

        <section className="card p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div className="section-header"><UserRound size={18} className="text-indigo-300" />{selected ? 'Edit student profile' : 'Create student identity'}</div>
            {selected && <button type="button" aria-label="Clear selected student" onClick={resetForm} className="text-slate-400 hover:text-white"><X size={16} /></button>}
          </div>
          <form onSubmit={event => { event.preventDefault(); setFormError(''); if (selected) updateStudent.mutate(); else createStudent.mutate(); }} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs text-slate-400">USN / Roll number<input required className="input-field mt-1" value={form.usn} onChange={event => setForm({ ...form, usn: event.target.value })} /></label>
            <label className="text-xs text-slate-400">College email<input required type="email" className="input-field mt-1" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></label>
            <label className="text-xs text-slate-400 sm:col-span-2">Full name<input required className="input-field mt-1" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label>
            {!selected && <label className="text-xs text-slate-400 sm:col-span-2">Initial password<input required type="password" minLength={8} autoComplete="new-password" className="input-field mt-1" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></label>}
            <label className="text-xs text-slate-400">Phone<input className="input-field mt-1" value={form.phone} onChange={event => setForm({ ...form, phone: event.target.value })} /></label>
            <label className="text-xs text-slate-400">Program<input required className="input-field mt-1" value={form.program} onChange={event => setForm({ ...form, program: event.target.value })} /></label>
            <label className="text-xs text-slate-400">Department<select required className="input-field mt-1" value={form.department_id} onChange={event => setForm({ ...form, department_id: event.target.value, section_id: '' })}>
              <option value="">Select department</option>{departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
            </select></label>
            <label className="text-xs text-slate-400">Semester<input required type="number" min="1" max="8" className="input-field mt-1" value={form.semester} onChange={event => setForm({ ...form, semester: event.target.value })} /></label>
            <label className="text-xs text-slate-400">Section<select required className="input-field mt-1" value={form.section_id} onChange={event => setForm({ ...form, section_id: event.target.value })}>
              <option value="">Select section</option>{sections.map(section => <option key={section.id} value={section.id}>{section.code}{section.synthetic ? ' · sample' : ''}</option>)}
            </select></label>
            <label className="text-xs text-slate-400">Admission year<input required type="number" min="1900" max="2100" className="input-field mt-1" value={form.admission_year} onChange={event => setForm({ ...form, admission_year: event.target.value })} /></label>
            <label className="text-xs text-slate-400">Academic status<select className="input-field mt-1" value={form.academic_status} onChange={event => setForm({ ...form, academic_status: event.target.value })}>
              <option value="ACTIVE">Active</option><option value="ON_LEAVE">On leave</option><option value="GRADUATED">Graduated</option><option value="WITHDRAWN">Withdrawn</option>
            </select></label>
            {selected && (
              <div className="sm:col-span-2 rounded-lg border border-slate-800 p-3 space-y-2">
                <label className="text-xs text-slate-400">Set a new password<input type="password" minLength={8} autoComplete="new-password" className="input-field mt-1" value={password} onChange={event => setPassword(event.target.value)} /></label>
                <button type="button" disabled={password.length < 8 || resetStudentPassword.isPending} className="btn-secondary inline-flex items-center gap-2 text-xs" onClick={() => resetStudentPassword.mutate()}>
                  <RotateCcw size={13} /> Reset password
                </button>
              </div>
            )}
            {formError && <p role="alert" className="sm:col-span-2 text-sm text-red-300 flex items-start gap-2"><AlertCircle size={15} className="mt-0.5 shrink-0" />{formError}</p>}
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" disabled={busy} className="btn-primary">{busy ? 'Saving…' : selected ? 'Save student' : 'Create student'}</button>
              {selected && <button type="button" className="btn-secondary" onClick={resetForm}>Cancel</button>}
            </div>
          </form>
        </section>
      </div>
    </div>
  );
};

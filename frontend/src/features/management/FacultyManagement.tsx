import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { AlertCircle, BookOpen, Plus, RotateCcw, Search, UserRound, X } from 'lucide-react';
import api from '../../api/client';

interface Department {
  id: string;
  name: string;
}

interface Faculty {
  id: string;
  employee_id: string | null;
  email: string | null;
  name: string | null;
  department_id: string;
  department: string;
  designation: string | null;
  subjects_taught: string[];
  sections_handled: string[];
  active: boolean;
  account_provisioned: boolean;
  synthetic: boolean;
}

interface FacultyForm {
  employee_id: string;
  email: string;
  password: string;
  name: string;
  department_id: string;
  designation: string;
}

const EMPTY_FORM: FacultyForm = {
  employee_id: '', email: '', password: '', name: '', department_id: '', designation: '',
};

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

export const FacultyManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [selected, setSelected] = useState<Faculty | null>(null);
  const [form, setForm] = useState<FacultyForm>(EMPTY_FORM);
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState('');
  const [formError, setFormError] = useState('');

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ['management-departments'],
    queryFn: async () => (await api.get('/management/departments')).data,
  });
  const { data, isLoading, isError } = useQuery<{ items: Faculty[]; total: number }>({
    queryKey: ['management-faculty', search, departmentFilter, activeFilter],
    queryFn: async () => (await api.get('/management/faculty', {
      params: {
        ...(search.trim() ? { q: search.trim() } : {}),
        ...(departmentFilter ? { department_id: departmentFilter } : {}),
        ...(activeFilter ? { active: activeFilter === 'active' } : {}),
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
    await queryClient.invalidateQueries({ queryKey: ['management-faculty'] });
  };
  const createFaculty = useMutation({
    mutationFn: async () => api.post('/management/faculty', form),
    onSuccess: async () => {
      setFeedback('Faculty identity created.');
      resetForm();
      await refresh();
    },
    onError: error => setFormError(errorMessage(error, 'Unable to create faculty identity.')),
  });
  const updateFaculty = useMutation({
    mutationFn: async () => {
      const profile = {
        employee_id: form.employee_id,
        email: form.email,
        name: form.name,
        department_id: form.department_id,
        designation: form.designation,
      };
      return api.patch(`/management/faculty/${encodeURIComponent(selected!.id)}`, selected?.account_provisioned
        ? profile
        : { ...profile, password: form.password });
    },
    onSuccess: async () => {
      setFeedback('Faculty profile updated.');
      resetForm();
      await refresh();
    },
    onError: error => setFormError(errorMessage(error, 'Unable to update faculty profile.')),
  });
  const setFacultyActive = useMutation({
    mutationFn: async (faculty: Faculty) => api.patch(`/management/faculty/${encodeURIComponent(faculty.id)}`, { active: !faculty.active }),
    onSuccess: async (_result, faculty) => {
      setFeedback(`${faculty.active ? 'Faculty account deactivated' : 'Faculty account reactivated'}.`);
      await refresh();
    },
    onError: error => setFeedback(errorMessage(error, 'Unable to update faculty status.')),
  });
  const resetFacultyPassword = useMutation({
    mutationFn: async () => api.post(`/management/faculty/${encodeURIComponent(selected!.id)}/password`, { password }),
    onSuccess: async () => {
      setPassword('');
      setFeedback('Faculty password reset.');
    },
    onError: error => setFormError(errorMessage(error, 'Unable to reset faculty password.')),
  });

  const beginEdit = (faculty: Faculty) => {
    setSelected(faculty);
    setForm({
      employee_id: faculty.employee_id || '',
      email: faculty.email || '',
      password: '',
      name: faculty.name || '',
      department_id: faculty.department_id,
      designation: faculty.designation || '',
    });
    setFormError('');
    setFeedback('');
  };
  const busy = createFaculty.isPending || updateFaculty.isPending;

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Institutional administration</p>
          <h1 className="text-2xl font-bold text-white mt-1">Faculty Management</h1>
          <p className="text-sm text-slate-400 mt-1">Maintain faculty identity and review schedule-derived teaching assignments.</p>
        </div>
        <button type="button" className="btn-primary flex items-center gap-2" onClick={resetForm}>
          <Plus size={16} /> Add faculty
        </button>
      </header>

      {feedback && <p role="status" className="text-sm text-emerald-300">{feedback}</p>}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.8fr)] gap-6">
        <section className="card p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="relative text-xs text-slate-400">
              Search
              <Search size={14} className="absolute left-3 top-8 text-slate-500" />
              <input className="input-field mt-1 pl-9" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name, employee ID, email" />
            </label>
            <label className="text-xs text-slate-400">Department
              <select className="input-field mt-1" value={departmentFilter} onChange={event => setDepartmentFilter(event.target.value)}>
                <option value="">All departments</option>
                {departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">Account
              <select className="input-field mt-1" value={activeFilter} onChange={event => setActiveFilter(event.target.value)}>
                <option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option>
              </select>
            </label>
          </div>
          {isError ? <p role="alert" className="text-sm text-red-300">Faculty records could not be loaded.</p>
            : isLoading ? <p className="text-sm text-slate-500">Loading faculty records…</p>
              : !data?.items.length ? <p className="text-sm text-slate-500 py-8 text-center">No faculty records match these filters.</p>
                : <div className="space-y-3">
                  {data.items.map(faculty => (
                    <article key={faculty.id} className="rounded-lg border border-slate-800 p-4">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                        <button type="button" className="text-left min-w-0" onClick={() => beginEdit(faculty)}>
                          <span className="block font-semibold text-white">{faculty.name || 'Name not provided'}</span>
                          <span className="block text-xs text-cyan-300 mt-1">{faculty.employee_id || 'Employee ID not provisioned'}</span>
                          <span className="block text-xs text-slate-500 mt-1">{faculty.email || 'No login account linked'} · {faculty.department}</span>
                        </button>
                        <div className="flex items-center gap-2">
                          {faculty.synthetic && <span className="badge-amber">Sample data</span>}
                          <span className={faculty.active ? 'badge-green' : 'badge-red'}>{faculty.account_provisioned ? (faculty.active ? 'Active' : 'Inactive') : 'No account'}</span>
                          {faculty.account_provisioned && <button type="button" className="text-xs text-indigo-300" onClick={() => setFacultyActive.mutate(faculty)}>{faculty.active ? 'Deactivate' : 'Reactivate'}</button>}
                        </div>
                      </div>
                      <p className="text-xs text-slate-400 mt-3">{faculty.designation || 'Designation not set'}</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 text-xs">
                        <p className="text-slate-400"><BookOpen size={13} className="inline mr-1 text-cyan-300" />Subjects: {faculty.subjects_taught.length ? faculty.subjects_taught.join(', ') : 'No timetable assignments'}</p>
                        <p className="text-slate-400">Sections: {faculty.sections_handled.length ? faculty.sections_handled.join(', ') : 'No timetable assignments'}</p>
                      </div>
                      <button type="button" className="text-xs text-indigo-300 mt-3" onClick={() => beginEdit(faculty)}>
                        {faculty.account_provisioned ? 'Edit profile' : 'Edit / provision login'}
                      </button>
                    </article>
                  ))}
                  <p className="text-xs text-slate-500">{data.total} record{data.total === 1 ? '' : 's'} · teaching assignments are read from the current timetable.</p>
                </div>}
        </section>

        <section className="card p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div className="section-header"><UserRound size={18} className="text-cyan-300" />{selected ? 'Edit faculty profile' : 'Create faculty identity'}</div>
            {selected && <button type="button" aria-label="Clear selected faculty" onClick={resetForm} className="text-slate-400 hover:text-white"><X size={16} /></button>}
          </div>
          <form onSubmit={event => { event.preventDefault(); setFormError(''); if (selected) updateFaculty.mutate(); else createFaculty.mutate(); }} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs text-slate-400">Employee ID<input required className="input-field mt-1" value={form.employee_id} onChange={event => setForm({ ...form, employee_id: event.target.value })} /></label>
            <label className="text-xs text-slate-400">College email<input required type="email" className="input-field mt-1" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></label>
            {(!selected || !selected.account_provisioned) && <label className="text-xs text-slate-400 sm:col-span-2">Initial password<input required type="password" minLength={8} autoComplete="new-password" className="input-field mt-1" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></label>}
            <label className="text-xs text-slate-400 sm:col-span-2">Full name<input required className="input-field mt-1" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label>
            <label className="text-xs text-slate-400">Department<select required className="input-field mt-1" value={form.department_id} onChange={event => setForm({ ...form, department_id: event.target.value })}>
              <option value="">Select department</option>{departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}
            </select></label>
            <label className="text-xs text-slate-400">Designation<input required className="input-field mt-1" value={form.designation} onChange={event => setForm({ ...form, designation: event.target.value })} /></label>
            {selected?.account_provisioned && (
              <div className="sm:col-span-2 rounded-lg border border-slate-800 p-3 space-y-2">
                <label className="text-xs text-slate-400">Set a new password<input type="password" minLength={8} autoComplete="new-password" className="input-field mt-1" value={password} onChange={event => setPassword(event.target.value)} /></label>
                <button type="button" disabled={password.length < 8 || resetFacultyPassword.isPending} className="btn-secondary inline-flex items-center gap-2 text-xs" onClick={() => resetFacultyPassword.mutate()}>
                  <RotateCcw size={13} /> Reset password
                </button>
              </div>
            )}
            {formError && <p role="alert" className="sm:col-span-2 text-sm text-red-300 flex items-start gap-2"><AlertCircle size={15} className="mt-0.5 shrink-0" />{formError}</p>}
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" disabled={busy} className="btn-primary">{busy ? 'Saving…' : selected ? 'Save faculty' : 'Create faculty'}</button>
              {selected && <button type="button" className="btn-secondary" onClick={resetForm}>Cancel</button>}
            </div>
          </form>
        </section>
      </div>
    </div>
  );
};

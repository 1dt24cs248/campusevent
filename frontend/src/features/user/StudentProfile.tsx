import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, GraduationCap } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { StudentProfileData } from './studentTypes';

const fields: Array<[keyof StudentProfileData, string]> = [
  ['full_name', 'Full name'],
  ['usn', 'USN / Roll number'],
  ['email', 'College email'],
  ['phone', 'Phone'],
  ['program', 'Program'],
  ['department', 'Department'],
  ['semester', 'Semester'],
  ['section', 'Section'],
  ['admission_year', 'Admission year'],
  ['academic_status', 'Academic status'],
];

export const StudentProfile: React.FC = () => {
  const { user } = useAuth();
  const { data: profile, isLoading, isError } = useQuery<StudentProfileData>({
    queryKey: ['student-profile', user?.id],
    queryFn: async () => (await api.get('/student/profile')).data,
    enabled: Boolean(user?.id),
  });

  return (
    <section className="max-w-4xl space-y-5">
      <header>
        <h1 className="section-header"><GraduationCap size={20} className="text-emerald-300" />My Profile</h1>
        <p className="text-sm text-slate-400 mt-2">Institutional information linked to your signed-in account.</p>
      </header>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading your profile…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Your profile could not be loaded.</div>
          : !profile ? <div className="card p-6 text-sm text-slate-400">A student profile has not been provisioned for this account.</div>
            : <dl className="card p-5 grid grid-cols-1 sm:grid-cols-2 gap-x-8">
              {fields.map(([key, label]) => {
                const value = profile[key];
                return (
                  <div key={key} className="py-4 border-b border-slate-800 last:border-0">
                    <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                    <dd className="text-sm text-slate-100 mt-1">{value === null || value === undefined || value === '' ? 'Not on record' : String(value)}</dd>
                  </div>
                );
              })}
            </dl>}
    </section>
  );
};

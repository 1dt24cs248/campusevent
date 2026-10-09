import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, BookOpen } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';

interface FacultyProfileData {
  full_name: string;
  employee_id?: string | null;
  email: string;
  department?: string | null;
  designation?: string | null;
  active: boolean;
}

const PROFILE_FIELDS: Array<[keyof FacultyProfileData, string]> = [
  ['full_name', 'Full name'],
  ['employee_id', 'Employee ID'],
  ['email', 'College email'],
  ['department', 'Department'],
  ['designation', 'Designation'],
  ['active', 'Account status'],
];

export const FacultyProfile: React.FC = () => {
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<FacultyProfileData>({
    queryKey: ['faculty-profile', user?.id],
    queryFn: async () => (await api.get('/faculty/profile')).data,
    enabled: Boolean(user?.id),
  });

  return (
    <section className="max-w-4xl space-y-5">
      <header>
        <h1 className="section-header"><BookOpen size={20} className="text-cyan-300" />My Faculty Profile</h1>
        <p className="text-sm text-slate-400 mt-2">Institutional details linked to your signed-in faculty account.</p>
      </header>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading your faculty profile…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Your profile could not be loaded.</div>
          : !data ? <div className="card p-6 text-sm text-slate-400">A faculty profile has not been provisioned for this account.</div>
            : <dl className="card p-5 grid grid-cols-1 sm:grid-cols-2 gap-x-8">
              {PROFILE_FIELDS.map(([key, label]) => (
                <div key={key} className="py-4 border-b border-slate-800 last:border-0">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                  <dd className="text-sm text-slate-100 mt-1">
                    {key === 'active' ? (data.active ? 'Active' : 'Inactive') : data[key] || 'Not on record'}
                  </dd>
                </div>
              ))}
            </dl>}
    </section>
  );
};

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ScrollText } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';

interface AuditRecord {
  id: string;
  actor_id: string;
  actor: string;
  role: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  summary: Record<string, unknown> | null;
  timestamp: string;
}

interface AuditPage {
  items: AuditRecord[];
  total: number;
}

export const ManagementAuditLog: React.FC = () => {
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<AuditPage>({
    queryKey: ['management-audit-log', user?.id],
    queryFn: async () => (await api.get('/management/audit-log', { params: { limit: 100 } })).data,
    enabled: Boolean(user?.id),
  });

  return (
    <section className="max-w-6xl space-y-5">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-indigo-300">Institutional governance</p>
        <h1 className="section-header mt-1"><ScrollText size={20} className="text-indigo-300" />Audit History</h1>
        <p className="text-sm text-slate-400 mt-2">Management changes recorded by existing audit workflows. Sensitive values such as passwords are not displayed.</p>
      </header>
      <div className="card p-5">
        {isLoading ? <p className="text-sm text-slate-400">Loading audit history…</p>
          : isError ? <p role="alert" className="text-sm text-red-300">Audit history could not be loaded.</p>
            : !data?.items.length ? <p className="text-sm text-slate-400">No management audit records are available.</p>
              : <>
                <p className="text-xs text-slate-500 mb-3">Showing {data.items.length} of {data.total} recorded actions.</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-slate-800 text-left text-xs text-slate-500">
                      <th className="py-3 pr-3">TIME</th><th className="pr-3">ACTOR</th><th className="pr-3">ACTION</th><th className="pr-3">RECORD</th><th>SUMMARY</th>
                    </tr></thead>
                    <tbody>{data.items.map(item => (
                      <tr key={item.id} className="border-b border-slate-800/60 align-top">
                        <td className="py-3 pr-3 whitespace-nowrap text-xs text-slate-400">{new Date(item.timestamp).toLocaleString()}</td>
                        <td className="py-3 pr-3 text-slate-200">{item.actor}<span className="block text-xs text-slate-500">{item.role || 'Role unavailable'} · {item.actor_id}</span></td>
                        <td className="py-3 pr-3 text-indigo-200">{item.action.replaceAll('_', ' ')}</td>
                        <td className="py-3 pr-3 text-slate-300">{item.entity_type}<span className="block max-w-40 truncate text-xs text-slate-500" title={item.entity_id}>{item.entity_id}</span></td>
                        <td className="py-3 text-xs text-slate-400">{item.summary ? JSON.stringify(item.summary) : 'No additional summary'}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </>}
      </div>
    </section>
  );
};

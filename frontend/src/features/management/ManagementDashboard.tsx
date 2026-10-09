import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import api from '../../api/client';
import {
  Activity, Users, AlertTriangle, Zap, CheckCircle,
  TrendingUp, BookOpen, BarChart3, Clock, ArrowRight, Info
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface StateOverview {
  total_rooms: number;
  allocatable_rooms: number;
  total_entries: number;
  allocated: number;
  at_risk: number;
  floating: number;
  capacity_violations: number;
  total_sections: number;
  total_faculty: number;
}

interface PublishedVersion {
  id: string;
  version_no: number;
  scenario_name?: string | null;
  published_at?: string | null;
  summary?: string | null;
}

interface ActionSummary {
  total: number;
  open: number;
  critical: number;
  in_progress: number;
  resolved_today: number;
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

const StatCard = ({
  title, value, sub, icon: Icon, iconBg, valueColor = 'text-white'
}: {
  title: string; value: string | number; sub?: string;
  icon: typeof Activity; iconBg: string; valueColor?: string;
}) => (
  <div className="stat-card">
    <div className={`stat-icon ${iconBg}`}>
      <Icon size={20} className="text-white" />
    </div>
    <div className="min-w-0">
      <p className="text-xs text-slate-500 font-medium">{title}</p>
      <p className={`text-2xl font-bold ${valueColor} leading-none mt-0.5`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  </div>
);

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm">
        <p className="text-slate-300 font-medium">{label}</p>
        {payload.map((p: any) => (
          <p key={p.dataKey} style={{ color: p.fill }} className="mt-1">
            {p.name}: {p.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export const ManagementDashboard: React.FC = () => {
  const navigate = useNavigate();

  const { data: overview, isLoading, isError } = useQuery<StateOverview>({
    queryKey: ['state-overview'],
    queryFn: async () => {
      const r = await api.get('/state/overview');
      return r.data;
    },
    refetchInterval: 30000,
  });

  const { data: scenarios } = useQuery<any[]>({
    queryKey: ['scenarios-list'],
    queryFn: async () => {
      const r = await api.get('/scenarios');
      return r.data;
    },
  });

  const { data: notifications } = useQuery<any[]>({
    queryKey: ['notifications-count'],
    queryFn: async () => {
      const r = await api.get('/notifications');
      return r.data;
    },
  });

  const { data: versions = [], isLoading: versionsLoading, isError: versionsError } = useQuery<PublishedVersion[]>({
    queryKey: ['published-versions'],
    queryFn: async () => {
      const r = await api.get('/versions');
      return r.data;
    },
  });

  const { data: actionSummary } = useQuery<ActionSummary>({
    queryKey: ['action-summary'],
    queryFn: async () => (await api.get('/reports/summary')).data,
  });

  const {
    data: managementOverview,
    isLoading: managementOverviewLoading,
    isError: managementOverviewError,
  } = useQuery<ManagementOverview>({
    queryKey: ['management-overview'],
    queryFn: async () => (await api.get('/management/overview')).data,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card h-24" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="card lg:col-span-2 h-64" />
          <div className="card h-64" />
        </div>
      </div>
    );
  }

  if (isError || !overview) {
    return (
      <div className="card p-8 max-w-2xl">
        <h1 className="text-xl font-bold text-white">Campus Overview</h1>
        <p role="alert" className="text-sm text-red-300 mt-3">The live campus overview could not be loaded. Check the API connection and try again.</p>
      </div>
    );
  }

  const utilizationRate = overview
    ? Math.round(((overview.allocated) / Math.max(overview.total_entries, 1)) * 100)
    : 0;

  const atRiskPct = overview
    ? Math.round((overview.at_risk / Math.max(overview.total_entries, 1)) * 100)
    : 0;

  // Build utilization chart data
  const utilizationData = overview ? [
    { name: 'OK', value: overview.allocated, fill: '#10b981' },
    { name: 'At Risk', value: overview.at_risk, fill: '#f59e0b' },
    { name: 'Floating', value: overview.floating, fill: '#6366f1' },
  ] : [];

  const recentScenarios = (scenarios || []).slice(0, 5);
  const unreadCount = (notifications || []).filter((n: any) => !n.read).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Campus Overview</h1>
          <p className="text-sm text-slate-400 mt-0.5">Block A — Live operational snapshot</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => navigate('/action-center')}
            className="btn-secondary flex items-center gap-2"
          >
            <AlertTriangle size={16} />
            Campus Action Center
          </button>
          <button
            onClick={() => navigate('/simulator')}
            className="btn-primary flex items-center gap-2"
          >
            <Zap size={16} />
            Launch What-If Simulator
          </button>
        </div>
      </div>

      <section aria-label="Institutional ERP overview" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wider text-indigo-300">Institutional ERP</p>
            <h2 className="text-lg font-semibold text-white mt-1">College operations snapshot</h2>
          </div>
          <Link to="/management/academics" className="text-sm text-indigo-300 hover:text-indigo-200">Manage academics →</Link>
        </div>
        {managementOverviewError
          ? <p role="alert" className="text-sm text-red-300">Institutional ERP counts could not be loaded.</p>
          : <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
            {[
              ['Students', managementOverview ? `${managementOverview.students.active} active / ${managementOverview.students.total}` : '—'],
              ['Faculty', managementOverview ? `${managementOverview.faculty.active} active / ${managementOverview.faculty.total}` : '—'],
              ['Departments', managementOverview?.departments],
              ['Active sections', managementOverview?.sections],
              ['Subjects', managementOverview?.subjects],
              ['Rooms', managementOverview?.rooms],
              ["Today's classes", managementOverview?.today_classes],
              ['Classroom requests', managementOverview?.pending_classroom_requests],
              ['Event proposals', managementOverview?.pending_event_proposals],
              ['Assessments due', managementOverview?.upcoming_assessments],
              ['Attendance today', managementOverview?.attendance_sessions_today],
              ['Announcements', managementOverview?.published_announcements],
            ].map(([label, value]) => (
              <article key={String(label)} className="card p-4">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-lg font-semibold text-white mt-1">
                  {managementOverviewLoading ? '…' : value ?? '—'}
                </p>
              </article>
            ))}
          </div>}
        <div className="flex flex-wrap gap-2">
          <Link to="/management/students" className="btn-secondary text-xs">Student records</Link>
          <Link to="/management/faculty" className="btn-secondary text-xs">Faculty records</Link>
          <Link to="/management/classroom-requests" className="btn-secondary text-xs">Review requests</Link>
          <Link to="/management/events" className="btn-secondary text-xs">Review events</Link>
          <Link to="/management/food" className="btn-secondary text-xs">Food administration</Link>
        </div>
      </section>

      <Link to="/action-center" className="card p-5 block hover:border-red-700/60 transition-colors">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-red-300">Campus Action Center</p>
            <h2 className="text-lg font-semibold text-white mt-1">Reports & incidents</h2>
            <p className="text-xs text-slate-400 mt-1">Triage real emergency, safety, maintenance, and general reports.</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 md:min-w-[440px]">
            {[
              ['Open', actionSummary?.open],
              ['Critical', actionSummary?.critical],
              ['In progress', actionSummary?.in_progress],
              ['Resolved today', actionSummary?.resolved_today],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-lg bg-slate-800/60 p-3">
                <p className="text-[11px] text-slate-500">{label}</p>
                <p className="text-xl font-bold text-white mt-1">{value ?? '—'}</p>
              </div>
            ))}
          </div>
        </div>
      </Link>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Timetable Entries"
          value={overview?.total_entries || 0}
          sub={`${overview?.allocated || 0} assigned`}
          icon={Activity}
          iconBg="bg-indigo-700"
        />
        <StatCard
          title="Active Sections"
          value={overview?.total_sections || 0}
          sub="From the live campus dataset"
          icon={BookOpen}
          iconBg="bg-cyan-700"
        />
        <StatCard
          title="Faculty Members"
          value={overview?.total_faculty || 0}
          icon={Users}
          iconBg="bg-purple-700"
        />
        <StatCard
          title="Capacity Violations"
          value={overview?.capacity_violations || 0}
          sub={`${atRiskPct}% of entries`}
          icon={AlertTriangle}
          iconBg="bg-amber-700"
          valueColor="text-amber-400"
        />
      </div>

      {/* Middle row: Utilization + Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Utilization Chart */}
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <div className="section-header">
              <BarChart3 size={18} className="text-indigo-400" />
              Room Assignment Breakdown
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-white">{utilizationRate}%</p>
              <p className="text-xs text-slate-500">assigned OK</p>
            </div>
          </div>

          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={utilizationData} barSize={40}>
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" name="Entries" radius={[4, 4, 0, 0]}>
                  {utilizationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="flex items-start gap-2 mt-4 p-3 bg-amber-900/20 border border-amber-700/30 rounded-lg">
            <Info size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-300">
              <span className="font-medium">{overview?.capacity_violations || 0} capacity violations</span> detected in home-room data (PROVIDED source).
              These represent real data-quality issues — strict CP-SAT constraints will resolve them during simulation.
            </p>
          </div>
        </div>

        {/* Quick Stats Card */}
        <div className="card p-6 space-y-4">
          <div className="section-header">
            <TrendingUp size={18} className="text-emerald-400" />
            Quick Stats
          </div>

          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-slate-800">
              <span className="text-sm text-slate-400">Total Rooms</span>
              <span className="font-semibold text-white">{overview?.total_rooms || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-800">
              <span className="text-sm text-slate-400">Allocatable</span>
              <span className="font-semibold text-emerald-400">{overview?.allocatable_rooms || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-800">
              <span className="text-sm text-slate-400">At Risk</span>
              <span className="font-semibold text-amber-400">{overview?.at_risk || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-slate-800">
              <span className="text-sm text-slate-400">Floating</span>
              <span className="font-semibold text-slate-400">{overview?.floating || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm text-slate-400">Notifications</span>
              <span className={`font-semibold ${unreadCount > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                {unreadCount} unread
              </span>
            </div>
          </div>

          <Link to="/notifications" className="btn-secondary w-full flex items-center justify-center gap-2 text-sm mt-2">
            <Bell size={14} /> View Notifications
          </Link>
        </div>
      </div>

      <section className="card p-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="section-header">
            <CheckCircle size={18} className="text-emerald-400" />
            Published timetable versions
          </div>
          <span className="badge-blue">{versions.length} versions</span>
        </div>
        {versionsLoading ? <p className="text-sm text-slate-500">Loading published versions…</p>
          : versionsError ? <p role="alert" className="text-sm text-red-300">Published versions could not be loaded.</p>
            : versions.length === 0 ? <p className="text-sm text-slate-500">No timetable versions have been published yet.</p>
              : <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-800">
                    <th className="text-left py-2 px-3 text-xs text-slate-500">VERSION</th>
                    <th className="text-left py-2 px-3 text-xs text-slate-500">SCENARIO</th>
                    <th className="text-left py-2 px-3 text-xs text-slate-500">SUMMARY</th>
                    <th className="text-left py-2 px-3 text-xs text-slate-500">PUBLISHED</th>
                  </tr></thead>
                  <tbody>{versions.slice(0, 5).map(version => (
                    <tr key={version.id} className="border-b border-slate-800/50">
                      <td className="py-3 px-3 text-emerald-300 font-semibold">v{version.version_no}</td>
                      <td className="py-3 px-3 text-slate-200">{version.scenario_name || 'Campus timetable'}</td>
                      <td className="py-3 px-3 text-slate-400 max-w-md truncate">{version.summary || 'Published timetable update'}</td>
                      <td className="py-3 px-3 text-slate-500 text-xs">{version.published_at ? new Date(version.published_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>}
      </section>

      {/* Scenario Activity */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="section-header">
            <Clock size={18} className="text-indigo-400" />
            Recent Scenario Activity
          </div>
          <button
            onClick={() => navigate('/simulator')}
            className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors"
          >
            New Scenario <ArrowRight size={12} />
          </button>
        </div>

        {recentScenarios.length === 0 ? (
          <div className="text-center py-10">
            <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center mx-auto mb-3">
              <Zap size={20} className="text-slate-600" />
            </div>
            <p className="text-slate-500 text-sm">No scenarios yet.</p>
            <p className="text-slate-600 text-xs mt-1">Launch the What-If Simulator to model campus decisions.</p>
            <button onClick={() => navigate('/simulator')} className="btn-primary mt-4 text-sm">
              Launch Simulator
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Scenario</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Category</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Created</th>
                </tr>
              </thead>
              <tbody>
                {recentScenarios.map((s: any) => (
                  <tr key={s.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-3">
                      <span className="font-medium text-slate-200">{s.name}</span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="badge-blue">{s.category || 'GENERAL'}</span>
                    </td>
                    <td className="py-3 px-3">
                      <span className={
                        s.status === 'PUBLISHED' ? 'badge-green' :
                        s.status === 'SIMULATED' ? 'badge-blue' :
                        s.status === 'APPROVED' ? 'badge-purple' :
                        'badge-amber'
                      }>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-500 text-xs">
                      {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* What-If CTA */}
      <div className="card p-6 bg-gradient-to-br from-indigo-900/40 to-slate-900 border-indigo-700/40">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Zap size={20} className="text-indigo-400" />
              What-If Decision Simulator
            </h3>
            <p className="text-sm text-slate-400 mt-1 max-w-xl">
              Ask "What happens if room A101 is unavailable?" — The CP-SAT optimizer runs in real time, 
              shows you alternatives, impact analysis, and lets you approve before publishing.
            </p>
            <div className="flex gap-4 mt-3 text-xs text-slate-500">
              <span className="flex items-center gap-1"><CheckCircle size={12} className="text-emerald-400" /> OR-Tools CP-SAT</span>
              <span className="flex items-center gap-1"><CheckCircle size={12} className="text-emerald-400" /> Multiple Strategies</span>
              <span className="flex items-center gap-1"><CheckCircle size={12} className="text-emerald-400" /> Auto-Notifications</span>
            </div>
          </div>
          <button
            onClick={() => navigate('/simulator')}
            className="btn-primary flex items-center gap-2 ml-6 flex-shrink-0"
          >
            <Zap size={16} />
            Open Simulator
          </button>
        </div>
      </div>
    </div>
  );
};

// Need Bell import
const Bell = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
  </svg>
);

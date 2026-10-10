import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Building2, LayoutDashboard, Zap, Bell, Bot, MapPin,
  GraduationCap, BookOpen, LogOut, ChevronLeft, ChevronRight,
  Calendar, Shield, Siren, ShieldAlert, Wrench, FileText, Utensils,
  ClipboardCheck, ClipboardList, Users, Building, ScrollText,
} from 'lucide-react';

const MANAGEMENT_NAV = [
  { href: '/management', icon: LayoutDashboard, label: 'Overview' },
  { href: '/simulator', icon: Zap, label: 'What-If Simulator' },
  { href: '/action-center', icon: LayoutDashboard, label: 'Campus Action Center' },
  { href: '/management/students', icon: GraduationCap, label: 'Student Management' },
  { href: '/management/faculty', icon: BookOpen, label: 'Faculty Management' },
  { href: '/management/faculty-subject-requests', icon: ClipboardList, label: 'Faculty Subject Requests' },
  { href: '/management/academics', icon: GraduationCap, label: 'Academic Management' },
  { href: '/management/audit', icon: ScrollText, label: 'Audit History' },
  { href: '/management/classroom-requests', icon: Building, label: 'Classroom Requests' },
  { href: '/management/events', icon: Calendar, label: 'Event Management' },
  { href: '/management/food', icon: Utensils, label: 'Food & Canteen' },
  { href: '/notifications', icon: Bell, label: 'Notifications' },
  { href: '/navigator', icon: MapPin, label: 'Campus Navigator' },
  { href: '/ai', icon: Bot, label: 'AI Assistant' },
];

const FACULTY_NAV = [
  { href: '/faculty', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/faculty/profile', icon: BookOpen, label: 'My Profile' },
  { href: '/faculty/subjects', icon: GraduationCap, label: 'My Subjects' },
  { href: '/faculty/subject-requests', icon: ClipboardList, label: 'Request Subjects' },
  { href: '/faculty/sections', icon: Users, label: 'My Sections' },
  { href: '/faculty/timetable', icon: Calendar, label: 'Teaching Timetable' },
  { href: '/faculty/attendance', icon: ClipboardCheck, label: 'Attendance' },
  { href: '/faculty/academics', icon: BookOpen, label: 'Assessments & Resources' },
  { href: '/faculty/classroom-requests', icon: Building, label: 'Classroom Requests' },
  { href: '/faculty/events', icon: Calendar, label: 'Upcoming Events' },
  { href: '/report?type=EMERGENCY', icon: Siren, label: 'Emergency / SOS' },
  { href: '/report?type=SAFETY', icon: ShieldAlert, label: 'Faculty safety concern' },
  { href: '/report?type=MAINTENANCE', icon: Wrench, label: 'Report facilities issue' },
  { href: '/reports', icon: FileText, label: 'My campus reports' },
  { href: '/food', icon: Utensils, label: 'Campus Food' },
  { href: '/notifications', icon: Bell, label: 'Notifications' },
  { href: '/navigator', icon: MapPin, label: 'Campus Navigator' },
  { href: '/ai', icon: Bot, label: 'AI Assistant' },
];

const STUDENT_NAV = [
  { href: '/student', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/student/profile', icon: GraduationCap, label: 'My Profile' },
  { href: '/student/academics', icon: BookOpen, label: 'My Academics' },
  { href: '/student/timetable', icon: Calendar, label: 'My Timetable' },
  { href: '/student/events', icon: Calendar, label: 'Upcoming Events' },
  { href: '/student/emergency', icon: Siren, label: 'Emergency Contacts / SOS' },
  { href: '/report?type=EMERGENCY', icon: Siren, label: 'Emergency / SOS' },
  { href: '/report?type=SAFETY', icon: ShieldAlert, label: 'Safety & Harassment' },
  { href: '/report?type=MAINTENANCE', icon: Wrench, label: 'Report Campus Issue' },
  { href: '/reports', icon: FileText, label: 'My Reports' },
  { href: '/food', icon: Utensils, label: 'Campus Food' },
  { href: '/notifications', icon: Bell, label: 'Notifications' },
  { href: '/navigator', icon: MapPin, label: 'Campus Navigator' },
  { href: '/ai', icon: Bot, label: 'AI Assistant' },
];

const ROLE_NAV: Record<string, typeof MANAGEMENT_NAV> = {
  MANAGEMENT: MANAGEMENT_NAV,
  FACULTY: FACULTY_NAV,
  STUDENT: STUDENT_NAV,
};

const ROLE_BADGE: Record<string, { label: string; className: string; icon: typeof Shield }> = {
  MANAGEMENT: { label: 'Management', className: 'badge-purple', icon: Shield },
  FACULTY: { label: 'Faculty', className: 'badge-blue', icon: BookOpen },
  STUDENT: { label: 'Student', className: 'badge-green', icon: GraduationCap },
};

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const navItems = ROLE_NAV[user?.role || ''] || [];
  const roleBadge = ROLE_BADGE[user?.role || ''];
  const RoleIcon = roleBadge?.icon || Shield;
  const isNavItemActive = (href: string) => {
    const path = href.split('?')[0];
    return location.pathname === path
      || (!['/management', '/student', '/faculty'].includes(path)
        && location.pathname.startsWith(`${path}/`));
  };
  const activeLabel = navItems.find(({ href }) => isNavItemActive(href))?.label;

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-16' : 'w-60'} flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col transition-all duration-200`}
      >
        {/* Logo */}
        <div className={`h-16 flex items-center border-b border-slate-800 px-4 gap-3 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <Building2 size={16} className="text-white" />
          </div>
          {!collapsed && (
            <div>
              <p className="text-sm font-bold text-white leading-none">Campus</p>
              <p className="text-xs text-indigo-400 leading-none">Intelligence</p>
            </div>
          )}
        </div>

        {/* Nav Items */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map(({ href, icon: Icon, label }) => {
            const isActive = isNavItemActive(href);
            return (
              <Link
                key={href}
                to={href}
                className={`${isActive ? 'nav-link-active' : 'nav-link-inactive'} ${collapsed ? 'justify-center px-2' : ''}`}
                title={collapsed ? label : undefined}
              >
                <Icon size={17} className="flex-shrink-0" />
                {!collapsed && <span>{label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="border-t border-slate-800 p-3">
          {!collapsed && (
            <div className="mb-2 px-2">
              <p className="text-xs font-medium text-slate-300 truncate">{user?.full_name || user?.email}</p>
              {roleBadge && (
                <span className={`${roleBadge.className} mt-1 flex items-center gap-1`}>
                  <RoleIcon size={10} />
                  {roleBadge.label}
                </span>
              )}
            </div>
          )}
          <div className={`flex ${collapsed ? 'flex-col items-center' : 'items-center justify-between'} gap-1`}>
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
            <button
              onClick={logout}
              className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition-colors"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-16 bg-slate-900/80 backdrop-blur border-b border-slate-800 flex items-center justify-between px-6 flex-shrink-0">
          <div>
            <h1 className="text-sm font-semibold text-slate-200">
              {activeLabel || 'Campus Intelligence'}
            </h1>
            <p className="text-xs text-slate-500">Block A Pilot Implementation</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Backend connected" />
            <span className="text-xs text-slate-500">Live</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

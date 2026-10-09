import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, ArrowLeft, BookOpen } from 'lucide-react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { StudentSubject } from './studentTypes';

interface StudentAcademicsData {
  subjects: StudentSubject[];
  message?: string | null;
  program?: string | null;
  department?: string | null;
  semester?: number | null;
  section?: string | null;
  attendance_available: boolean;
  upcoming_assessments: AcademicAssessment[];
  announcements: { id: string; title: string; body: string; published_at: string }[];
}

interface StudentSubjectDetails extends StudentSubject {
  section: string;
  syllabus: { module_number: number; title: string; description?: string | null; is_synthetic: boolean }[];
  resources: { id: string; title: string; description?: string | null; resource_type: string; url?: string | null; is_synthetic: boolean }[];
  assessments: AcademicAssessment[];
  marks: { assessment_id: string; assessment_title: string; kind: string; date: string; marks: number; maximum_marks: number; percentage: number }[];
  attendance_message?: string | null;
}

interface AcademicAssessment {
  id: string;
  title: string;
  kind: string;
  date: string;
  description?: string | null;
  maximum_marks?: number | null;
  is_synthetic: boolean;
}

export const StudentAcademics: React.FC = () => {
  const { user } = useAuth();
  const { data, isLoading, isError } = useQuery<StudentAcademicsData>({
    queryKey: ['student-academics', user?.id],
    queryFn: async () => (await api.get('/student/academics')).data,
    enabled: Boolean(user?.id),
  });

  return (
    <section className="max-w-5xl space-y-5">
      <header>
        <h1 className="section-header"><BookOpen size={20} className="text-indigo-300" />My Academics</h1>
        <p className="text-sm text-slate-400 mt-2">
          {[data?.program, data?.department, data?.semester ? `Semester ${data.semester}` : null, data?.section ? `Section ${data.section}` : null].filter(Boolean).join(' · ') || 'Your academic record'}
        </p>
      </header>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading your subjects…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Academic information could not be loaded.</div>
          : !data?.subjects.length ? <div className="card p-8 text-center text-sm text-slate-400">{data?.message || 'Academic information has not been published yet.'}</div>
            : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.subjects.map(subject => (
                  <Link key={subject.id} to={`/student/academics/${encodeURIComponent(subject.id)}`} className="card p-5 hover:border-indigo-700/70 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-indigo-300">{subject.code}</p>
                        <h2 className="font-semibold text-white mt-1">{subject.name}</h2>
                      </div>
                      {subject.demo_data && <span className="badge-amber">DEMO DATA</span>}
                    </div>
                    <p className="text-xs text-slate-400 mt-3">Faculty: {subject.faculty.length ? subject.faculty.join(', ') : 'Not listed'}</p>
                    {subject.kind && <p className="text-xs text-slate-500 mt-1">Class type: {subject.kind}</p>}
                    {subject.credits != null && <p className="text-xs text-slate-500 mt-1">Credits: {subject.credits}</p>}
                    <p className="text-xs text-slate-400 mt-2">
                      Attendance: {subject.attendance ? `${subject.attendance.percentage}% · ${subject.attendance.present} present / ${subject.attendance.absent} absent` : 'Not entered yet'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">{subject.upcoming_assessments || 0} upcoming assessments · {subject.resources_count || 0} resources</p>
                    <p className="text-xs text-indigo-300 mt-4">View available details</p>
                  </Link>
                ))}
              </div>
            )}
      {data?.upcoming_assessments.length ? (
        <div className="card p-5">
          <h2 className="font-semibold text-slate-200">Upcoming assessments</h2>
          <ul className="mt-3 space-y-2">{data.upcoming_assessments.map(item => (
            <li key={item.id} className="flex justify-between gap-3 text-sm">
              <span className="text-slate-200">{item.title} <span className="text-slate-500">· {item.kind}</span></span>
              <time className="text-slate-400">{new Date(item.date).toLocaleDateString()}</time>
            </li>
          ))}</ul>
        </div>
      ) : <div className="card p-4 text-sm text-slate-400">No upcoming assessments have been published.</div>}
      <div className="card p-5">
        <h2 className="font-semibold text-slate-200">Academic announcements</h2>
        {data?.announcements.length
          ? <ul className="mt-3 space-y-3">{data.announcements.map(item => <li key={item.id} className="border-t border-slate-800 pt-3"><p className="text-sm font-medium text-white">{item.title}</p><p className="text-sm text-slate-300 mt-1 whitespace-pre-wrap">{item.body}</p><time className="text-xs text-slate-500">{new Date(item.published_at).toLocaleString()}</time></li>)}</ul>
          : <p className="text-sm text-slate-400 mt-2">No academic announcements are available for your section.</p>}
      </div>
    </section>
  );
};

export const StudentSubjectDetail: React.FC = () => {
  const { subjectId = '' } = useParams();
  const { user } = useAuth();
  const { data: subject, isLoading, isError } = useQuery<StudentSubjectDetails>({
    queryKey: ['student-subject', user?.id, subjectId],
    queryFn: async () => (await api.get(`/student/academics/${encodeURIComponent(subjectId)}`)).data,
    enabled: Boolean(user?.id && subjectId),
  });

  return (
    <section className="max-w-3xl space-y-5">
      <Link to="/student/academics" className="inline-flex items-center gap-2 text-sm text-indigo-300 hover:text-indigo-200"><ArrowLeft size={15} />Back to My Academics</Link>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading subject details…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />This subject is unavailable in your section.</div>
          : !subject ? <div className="card p-6 text-sm text-slate-400">Subject information is not available.</div>
            : (
              <article className="card p-6 space-y-5">
                <header>
                  <p className="text-sm font-semibold text-indigo-300">{subject.code}</p>
                  <h1 className="text-2xl font-bold text-white mt-1">{subject.name}</h1>
                  <p className="text-sm text-slate-400 mt-2">Your section: {subject.section}</p>
                  {subject.demo_data && <span className="badge-amber mt-3">DEMO DATA</span>}
                </header>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div><dt className="text-xs text-slate-500">Faculty</dt><dd className="text-sm text-slate-200 mt-1">{subject.faculty.length ? subject.faculty.join(', ') : 'Not listed'}</dd></div>
                  {subject.kind && <div><dt className="text-xs text-slate-500">Class type</dt><dd className="text-sm text-slate-200 mt-1">{subject.kind}</dd></div>}
                  {subject.credits != null && <div><dt className="text-xs text-slate-500">Credits</dt><dd className="text-sm text-slate-200 mt-1">{subject.credits}</dd></div>}
                </dl>
                {subject.description && <p className="text-sm text-slate-300">{subject.description}</p>}
                <section>
                  <h2 className="font-semibold text-slate-200">Attendance</h2>
                  {subject.attendance
                    ? <p className="mt-2 text-sm text-slate-300">{subject.attendance.present} present · {subject.attendance.absent} absent · {subject.attendance.total_classes} recorded classes · {subject.attendance.percentage}%</p>
                    : <p className="mt-2 text-sm text-slate-400">{subject.attendance_message || 'Attendance records have not been entered yet.'}</p>}
                </section>
                <section>
                  <h2 className="font-semibold text-slate-200">Syllabus</h2>
                  {subject.syllabus.length
                    ? <ol className="mt-2 space-y-2">{subject.syllabus.map(module => <li key={`${module.module_number}-${module.title}`} className="rounded-lg bg-slate-800/50 p-3"><p className="text-sm text-slate-200">Module {module.module_number} · {module.title}{module.is_synthetic && <span className="badge-amber ml-2">SYNTHETIC</span>}</p>{module.description && <p className="text-xs text-slate-400 mt-1">{module.description}</p>}</li>)}</ol>
                    : <p className="mt-2 text-sm text-slate-400">Syllabus information has not been published yet.</p>}
                </section>
                <section>
                  <h2 className="font-semibold text-slate-200">Resources</h2>
                  {subject.resources.length
                    ? <ul className="mt-2 space-y-2">{subject.resources.map(resource => <li key={resource.id} className="rounded-lg bg-slate-800/50 p-3"><p className="text-sm text-slate-200">{resource.title} <span className="text-xs text-slate-500">· {resource.resource_type}</span>{resource.is_synthetic && <span className="badge-amber ml-2">SYNTHETIC</span>}</p>{resource.description && <p className="text-xs text-slate-400 mt-1">{resource.description}</p>}{resource.url && /^https?:\/\//i.test(resource.url) && <a href={resource.url} target="_blank" rel="noreferrer" className="text-xs text-indigo-300 break-all">{resource.url}</a>}</li>)}</ul>
                    : <p className="mt-2 text-sm text-slate-400">No resources have been published for your section.</p>}
                </section>
                <section>
                  <h2 className="font-semibold text-slate-200">Assessments & marks</h2>
                  {subject.assessments.length
                    ? <div className="mt-2 space-y-2">{subject.assessments.map(item => {
                      const mark = subject.marks.find(row => row.assessment_id === item.id);
                      return <article key={item.id} className="rounded-lg bg-slate-800/50 p-3"><p className="text-sm text-slate-200">{item.title} · {item.kind}</p><p className="text-xs text-slate-400 mt-1">{new Date(item.date).toLocaleDateString()}{item.maximum_marks != null ? ` · Maximum ${item.maximum_marks}` : ''}</p>{mark ? <p className="text-sm text-emerald-300 mt-2">{mark.marks} / {mark.maximum_marks} ({mark.percentage}%)</p> : <p className="text-xs text-slate-500 mt-2">Marks have not been published yet.</p>}</article>;
                    })}</div>
                    : <p className="mt-2 text-sm text-slate-400">Assessment data is not available yet.</p>}
                </section>
              </article>
            )}
    </section>
  );
};
